using System.Linq;
using System.Text.Json;
using System.Collections.Generic;
using System;
using Aura.Revit.Models;

namespace Aura.Revit.Services
{
    /// <summary>
    /// Processes the precise element-level LCA returns from the Aura API
    /// and formats them into the JSON Payload expected by the web UI dashboard.
    /// </summary>
    public static class LcaAggregator
    {
        public static string BuildWebPayload(string projectName, AuraApiResponse apiResponse, SyncPayload sentData)
        {
            if (apiResponse == null || apiResponse.Elements == null) return "{}";

            // 1. Join API results with sent Revit Element Categories
            var joinedData = apiResponse.Elements.Join(
                sentData.Elements,
                r => r.Id,
                e => e.Id,
                (r, e) => new { Result = r, Category = e.Category, Name = e.MaterialName }
            ).ToList();

            // 2. Metrics Totals
            double totalFP = joinedData.Sum(x => x.Result.Metrics?.TotalEmbodiedKg ?? 0) / 1000.0;
            double upfrontFP = joinedData.Sum(x => x.Result.Metrics?.TotalUpfrontKg ?? 0) / 1000.0;
            double sumVol = joinedData.Sum(x => x.Result.Metrics?.VolumeM3 ?? 0);
            double upfrontInt = sumVol > 0 ? (upfrontFP * 1000) / sumVol : 0;
            double embodiedInt = sumVol > 0 ? (totalFP * 1000) / sumVol : 0;

            // Target Alignment Variables
            double dummyGia = 6400; // Hardcoded fallback for now
            double currentScore = totalFP > 0 ? (totalFP * 1000) / dummyGia : 0;
            string rating = GetScoreFormat(currentScore);

            // 3. Phases
            var phasesObj = new Dictionary<string, double>
            {
                { "A0", 0.0 },
                { "A1-A3", joinedData.Sum(x => x.Result.Metrics?.Co2A1A3 ?? 0) / 1000.0 },
                { "A4", joinedData.Sum(x => x.Result.Metrics?.Co2A4 ?? 0) / 1000.0 },
                { "A5", joinedData.Sum(x => x.Result.Metrics?.Co2A5 ?? 0) / 1000.0 },
                { "C1-C4", joinedData.Sum(x => x.Result.Metrics?.Co2C1C4 ?? 0) / 1000.0 },
                { "Sequestration", joinedData.Sum(x => x.Result.Metrics?.Co2Seq ?? 0) / 1000.0 }
            };

            // 4. Equivalencies
            var equivalencies = new
            {
                carsPerYear = Math.Round((totalFP * 1000) / 1.8), // dummy math
                flightsLonNY = Math.Round((totalFP * 1000) / 2.22),
                trees30Years = Math.Round((totalFP * 1000) / 0.025),
                socialCarbonCostStr = $"£ {Math.Round((totalFP * 1000) * 0.15):N2}"
            };

            // 5. Material Summaries (Concrete, Steel, Timber)
            var materialSums = joinedData
                .GroupBy(x => GetSimulatedMaterialClass(x.Name))
                .Select(g => new
                {
                    matClass = g.Key,
                    totalMass = g.Sum(x => x.Result.Metrics?.MassKg ?? 0) / 1000.0,
                    avgIntensity = g.Sum(x => x.Result.Metrics?.VolumeM3 ?? 0) > 0 
                        ? g.Sum(x => x.Result.Metrics?.TotalEmbodiedKg ?? 0) / g.Sum(x => x.Result.Metrics?.VolumeM3 ?? 0)
                        : 0
                }).ToList();

            // 6. Build Final Shape matching mockData.js
            var webModel = new
            {
                overview = new
                {
                    projectName = string.IsNullOrWhiteSpace(projectName) ? "Project" : projectName,
                    calculatedCarbonFootprint = totalFP,
                    phases = phasesObj,
                    intensities = new { upfrontFootprint = upfrontFP, upfrontIntensity = upfrontInt, embodiedFootprint = totalFP, embodiedIntensity = embodiedInt },
                    equivalents = equivalencies,
                    targetAlignment = new { buildingType = "IStructE", totalGIA = dummyGia, newGIA = dummyGia, targetScore = 150, currentScore = Math.Round(currentScore, 1), ratingFormat = rating },
                    materialSummaries = materialSums
                },
                pieCharts = new
                {
                    byCategory = joinedData.GroupBy(x => x.Category).Select(g => new {
                        label = g.Key,
                        value = g.Sum(x => x.Result.Metrics?.TotalEmbodiedKg ?? 0) / 1000.0,
                        color = GetRandomColor(g.Key)
                    }).ToList(),
                    byPhase = phasesObj.Where(x => x.Value > 0).Select((k, i) => new {
                        label = k.Key,
                        value = k.Value,
                        color = GetPhaseColor(k.Key)
                    }).ToList()
                },
                histogram = new {
                    materials = joinedData.OrderBy(x => x.Result.Metrics?.TotalEmbodiedKg ?? 0).Select(x => new {
                        name = $"{x.Result.Metrics?.Material ?? "Unk"} ({x.Result.Id})",
                        value = (x.Result.Metrics?.TotalEmbodiedKg ?? 0) / 1000.0,
                        intensity = x.Result.Status == "Warning" ? "High" : "Low"
                    }).ToList()
                },
                calculation = new {
                    groups = joinedData.GroupBy(x => x.Category).Select(catGroup => new {
                        category = catGroup.Key,
                        materials = catGroup.GroupBy(m => m.Result.Metrics?.Material ?? "Unk").Select(matGroup => new {
                            mat = matGroup.Key,
                            vol = matGroup.Sum(y => y.Result.Metrics?.VolumeM3 ?? 0).ToString("F3"),
                            totVol = matGroup.Sum(y => y.Result.Metrics?.VolumeM3 ?? 0).ToString("F3"),
                            density = matGroup.First().Result.Metrics?.MassKg > 0 ? Math.Round(matGroup.First().Result.Metrics!.MassKg / matGroup.First().Result.Metrics!.VolumeM3, 1) : 0,
                            mass = matGroup.Sum(y => y.Result.Metrics?.MassKg ?? 0).ToString("F1"),
                            co2Int = matGroup.First().Result.Metrics?.TotalEmbodiedKg > 0 ? Math.Round(matGroup.First().Result.Metrics!.TotalEmbodiedKg / matGroup.First().Result.Metrics!.MassKg, 2) : 0,
                            total = (matGroup.Sum(y => y.Result.Metrics?.TotalEmbodiedKg ?? 0) / 1000.0).ToString("F2"),
                            pct = totalFP > 0 ? Math.Round(((matGroup.Sum(y => y.Result.Metrics?.TotalEmbodiedKg ?? 0) / 1000.0) / totalFP) * 100, 1) : 0
                        }).ToList()
                    }).ToList(),
                    elements = joinedData.Select(x => new {
                        id = x.Result.Id,
                        category = x.Category,
                        name = "Element",
                        matName = x.Result.Metrics?.Material ?? "Unk",
                        level = "Unk",
                        vol = Math.Round(x.Result.Metrics?.VolumeM3 ?? 0, 3),
                        ecTotal = Math.Round(x.Result.Metrics?.TotalEmbodiedKg ?? 0, 2)
                    }).ToList()
                }
            };

            return JsonSerializer.Serialize(webModel, new JsonSerializerOptions { PropertyNamingPolicy = JsonNamingPolicy.CamelCase });
        }

        private static string GetRandomColor(string seed)
        {
            var colors = new[] { "#9F7A7A", "#6AA8A4", "#D1D343", "#5F9EA0", "#90EE90", "#ADD8E6" };
            return colors[Math.Abs(seed.GetHashCode()) % colors.Length];
        }

        private static string GetPhaseColor(string phase)
        {
            if (phase.Contains("A1")) return "#9F7A7A";
            if (phase == "A4") return "#6AA8A4";
            if (phase == "A5") return "#D1D343";
            return "#54C8CE";
        }

        private static string GetScoreFormat(double score)
        {
            if (score < 50) return "A++";
            if (score < 100) return "A+";
            if (score < 150) return "A";
            if (score < 200) return "B";
            if (score < 250) return "C";
            if (score < 300) return "D";
            if (score < 350) return "E";
            if (score < 400) return "F";
            return "G";
        }

        private static string GetSimulatedMaterialClass(string matName)
        {
            if (string.IsNullOrEmpty(matName)) return "Other";
            string lower = matName.ToLowerInvariant();
            if (lower.Contains("concrete") || lower.Contains("concreto") || lower.Contains("cimento")) return "Concrete";
            if (lower.Contains("steel") || lower.Contains("aço") || lower.Contains("metal") || lower.Contains("iron")) return "Steel";
            if (lower.Contains("timber") || lower.Contains("wood") || lower.Contains("madeira")) return "Timber";
            return "Other";
        }
    }
}
