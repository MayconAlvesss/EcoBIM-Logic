using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.Revit.DB;
using RevitColor = Autodesk.Revit.DB.Color;
using RevitView  = Autodesk.Revit.DB.View;

namespace Aura.Revit.Services
{
    /// <summary>
    /// Applies premium visual overrides to the active Revit 3D view:
    ///
    ///   â€¢ Semi-transparent coloured surfaces (so you see geometry through walls)
    ///   â€¢ Bold, bright projection edges per category
    ///   â€¢ Cut pattern in a contrasting solid colour
    ///   â€¢ Adapts line weight to the view's Detail Level
    ///
    /// Reference: the orange/magenta/yellow building shown in the EcoBIM spec image.
    /// </summary>
    public static class HeatmapVisualizer
    {
        // â”€â”€ Categories we colour â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        private static readonly BuiltInCategory[] TARGET_CATS =
        {
            BuiltInCategory.OST_Walls,
            BuiltInCategory.OST_StructuralColumns,
            BuiltInCategory.OST_StructuralFraming,
            BuiltInCategory.OST_StructuralFoundation,
            BuiltInCategory.OST_Floors,
            BuiltInCategory.OST_Roofs,
        };

        // â”€â”€ Category palette â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        // Surface fill = semi-transparent; edge = vivid matching hue.
        // Colours tuned to match the reference "beautiful heatmap" image.
        private static readonly Dictionary<BuiltInCategory, (RevitColor Fill, RevitColor Edge, int Transparency)> CAT_STYLE
            = new()
        {
            // Warm orange walls â€” solid enough to read, transparent enough for depth
            [BuiltInCategory.OST_Walls] =
                (new RevitColor(255, 140, 30), new RevitColor(220, 90, 0), 55),

            // Bright yellow-orange floors (semi-transparent so you see through them)
            [BuiltInCategory.OST_Floors] =
                (new RevitColor(255, 210, 0), new RevitColor(200, 160, 0), 65),

            // Vivid magenta/pink structural framing â€” stands out against everything
            [BuiltInCategory.OST_StructuralFraming] =
                (new RevitColor(255, 30, 160), new RevitColor(200, 0, 120), 45),

            // Orange-red columns
            [BuiltInCategory.OST_StructuralColumns] =
                (new RevitColor(255, 90, 0), new RevitColor(200, 50, 0), 40),

            // Deep red foundations / piles
            [BuiltInCategory.OST_StructuralFoundation] =
                (new RevitColor(200, 20, 20), new RevitColor(140, 0, 0), 30),

            // Amber roof â€” slightly distinct from walls
            [BuiltInCategory.OST_Roofs] =
                (new RevitColor(210, 120, 0), new RevitColor(160, 80, 0), 60),
        };

        // â”€â”€ Carbon-intensity ramp colours â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        // Used when real WLCA data is available (Sync & Analyze).
        // Surfaces are still semi-transparent; edges remain vivid.
        private static readonly (double MaxIntensity, RevitColor Fill, RevitColor Edge)[] RAMP =
        {
            (150,  new RevitColor(255, 240,   0), new RevitColor(200, 180,   0)),   // Yellow   < 150
            (250,  new RevitColor(255, 195,   0), new RevitColor(200, 140,   0)),   // L-Orange < 250
            (350,  new RevitColor(255, 128,   0), new RevitColor(200,  90,   0)),   // Orange   < 350
            (450,  new RevitColor(255,  69,   0), new RevitColor(200,  40,   0)),   // R-Orange < 450
            (550,  new RevitColor(220,  20,  60), new RevitColor(160,   0,  30)),   // Red      < 550
            (800,  new RevitColor(160,  20,  20), new RevitColor(100,   0,   0)),   // Dark Red < 800
            (9999, new RevitColor(148,   0, 211), new RevitColor( 90,   0, 160)),   // Purple   > 800
        };

        // â”€â”€ Public: category-based preview (no API data needed) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        /// <summary>
        /// Immediately colours all structural/architectural elements by Revit category.
        /// Works without any API call. Returns the number of elements coloured.
        /// </summary>
        public static int ApplyCategoryFallback(Document doc, RevitView activeView)
        {
            EnsureIs3D(activeView);
            var solidId = RequireSolidFill(doc);

            int lineWeight = GetAdaptiveLineWeight(activeView);
            int count = 0;

            using var t = new Transaction(doc, "Aura: Preview by Category");
            t.Start();

            // First reset all overrides so we start clean
            ResetAllOverrides(doc, activeView);
            ApplyHalftoneContext(doc, activeView, solidId);

            foreach (BuiltInCategory cat in TARGET_CATS)
            {
                if (!CAT_STYLE.TryGetValue(cat, out var style)) continue;

                var elems = CollectVisible(doc, activeView, cat);
                foreach (var elem in elems)
                {
                    var ogs = BuildOverride(style.Fill, style.Edge, style.Transparency,
                                           solidId, lineWeight);
                    activeView.SetElementOverrides(elem.Id, ogs);
                    count++;
                }
            }

            t.Commit();
            return count;
        }

        // â”€â”€ Public: WLCA carbon heatmap (with API data) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
        /// <summary>
        /// Applies the yellow-to-purple carbon intensity ramp.
        /// Elements not in parsedData fall back to their category colour.
        /// Returns the number of elements coloured.
        /// </summary>
        public static int ApplyCarbonHeatmap(Document doc, RevitView activeView, AuraApiResponse parsedData)
        {
            EnsureIs3D(activeView);
            var solidId = RequireSolidFill(doc);

            int lineWeight = GetAdaptiveLineWeight(activeView);

            // Build lookup: ElementId.Value â†’ carbon intensity (kgCO2e / m3)
            var intensityMap = new Dictionary<long, double>();
            foreach (var item in parsedData.Elements)
            {
                if (item.Metrics == null || item.Id <= 0) continue;
                double kg  = item.Metrics.TotalEmbodiedKg;
                double vol = item.Metrics.VolumeM3;
                if (kg > 0 && vol > 0.001)
                    intensityMap[item.Id] = kg / vol;
            }

            int count = 0;

            using var t = new Transaction(doc, "Aura: WLCA Carbon Heatmap");
            t.Start();

            ResetAllOverrides(doc, activeView);
            ApplyHalftoneContext(doc, activeView, solidId);

            foreach (BuiltInCategory cat in TARGET_CATS)
            {
                var catStyle   = CAT_STYLE.TryGetValue(cat, out var cs) ? cs : default;
                var elems      = CollectVisible(doc, activeView, cat);

                foreach (var elem in elems)
                {
                    OverrideGraphicSettings ogs;

                    if (intensityMap.TryGetValue(elem.Id.Value, out double intensity))
                    {
                        // Use ramp colour derived from carbon intensity
                        var ramp = GetRampEntry(intensity);
                        ogs = BuildOverride(ramp.Fill, ramp.Edge, 55, solidId, lineWeight);
                    }
                    else
                    {
                        // Element not in API results â€” use soft category colour
                        if (catStyle.Fill == null) continue;
                        ogs = BuildOverride(catStyle.Fill, catStyle.Edge,
                                            catStyle.Transparency + 15, solidId, lineWeight);
                    }

                    activeView.SetElementOverrides(elem.Id, ogs);
                    count++;
                }
            }

            t.Commit();
            return count;
        }

        /// <summary>
        /// Clears all visual overrides from the active view, restoring the original look.
        /// </summary>
        public static void ClearAllOverrides(Document doc, RevitView activeView)
        {
            EnsureIs3D(activeView);

            using var t = new Transaction(doc, "Aura: Clear Overrides");
            t.Start();
            
            // Remove overrides from ALL elements in the view
            var allElems = new FilteredElementCollector(doc, activeView.Id)
                                .WhereElementIsNotElementType()
                                .ToElements();
            
            var clean = new OverrideGraphicSettings();
            foreach(var e in allElems)
            {
                activeView.SetElementOverrides(e.Id, clean);
            }
            
            t.Commit();
        }

        // â”€â”€ Private helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

        private static OverrideGraphicSettings BuildOverride(
            RevitColor fill, RevitColor edge, int transparency, ElementId solidId, int lineWeight)
        {
            var ogs = new OverrideGraphicSettings();

            // â”€ Surface (projection / shaded face) â”€
            ogs.SetSurfaceForegroundPatternId(solidId);
            ogs.SetSurfaceForegroundPatternColor(fill);
            ogs.SetSurfaceTransparency(Math.Clamp(transparency, 0, 95));

            // â”€ Cut (section / plan cut) â”€
            ogs.SetCutForegroundPatternId(solidId);
            ogs.SetCutForegroundPatternColor(fill);

            // â”€ Projection edges (visible in 3D) â”€
            // Bold, vivid edge colour â€” this is what makes elements "pop"
            ogs.SetProjectionLineColor(edge);
            ogs.SetProjectionLineWeight(lineWeight);

            // â”€ Cut edges â”€
            ogs.SetCutLineColor(edge);
            ogs.SetCutLineWeight(lineWeight);

            return ogs;
        }

        /// <summary>
        /// Edge line weight scaled to the view's detail level so that coarse
        /// views still look great and fine views don't become too heavy.
        /// Revit accepts 1-16 (pen weight table index).
        /// </summary>
        private static int GetAdaptiveLineWeight(RevitView view)
        {
            return view.DetailLevel switch
            {
                ViewDetailLevel.Coarse  => 5,
                ViewDetailLevel.Medium  => 6,
                ViewDetailLevel.Fine    => 8,
                _                      => 6,
            };
        }

        private static (RevitColor Fill, RevitColor Edge) GetRampEntry(double intensity)
        {
            foreach (var r in RAMP)
                if (intensity <= r.MaxIntensity)
                    return (r.Fill, r.Edge);
            return (RAMP[^1].Fill, RAMP[^1].Edge);
        }

        private static IList<Element> CollectVisible(Document doc, RevitView view, BuiltInCategory cat)
            => new FilteredElementCollector(doc, view.Id)
                   .OfCategory(cat)
                   .WhereElementIsNotElementType()
                   .ToElements();

        /// <summary>Remove all Aura overrides so we start from a clean state.</summary>
        private static void ResetAllOverrides(Document doc, RevitView view)
        {
            var clean = new OverrideGraphicSettings();
            var allElems = new FilteredElementCollector(doc, view.Id)
                                .WhereElementIsNotElementType()
                                .ToElements();
            foreach (var elem in allElems)
                view.SetElementOverrides(elem.Id, clean);
        }

        private static void ApplyHalftoneContext(Document doc, RevitView view, ElementId solidId)
        {
            var ogs = new OverrideGraphicSettings();
            ogs.SetHalftone(true);
            ogs.SetSurfaceTransparency(80); // Quase invisível
            ogs.SetSurfaceForegroundPatternId(solidId);
            ogs.SetSurfaceForegroundPatternColor(new RevitColor(220, 220, 220));
            ogs.SetProjectionLineColor(new RevitColor(180, 180, 180));
            ogs.SetProjectionLineWeight(1);

            var allElems = new FilteredElementCollector(doc, view.Id)
                                .WhereElementIsNotElementType()
                                .ToElements();

            foreach(var elem in allElems)
            {
                if (elem.Category == null) continue;
                BuiltInCategory cat = (BuiltInCategory)elem.Category.Id.Value;
                if (!TARGET_CATS.Contains(cat))
                {
                    try { view.SetElementOverrides(elem.Id, ogs); } catch { }
                }
            }
        }

        private static void EnsureIs3D(RevitView view)
        {
            if (view is not View3D)
                throw new InvalidOperationException(
                    "Aura heatmap requires an active 3D view. Please switch to a 3D view and try again.");
        }

        private static ElementId RequireSolidFill(Document doc)
        {
            var pattern = new FilteredElementCollector(doc)
                .OfClass(typeof(FillPatternElement))
                .Cast<FillPatternElement>()
                .FirstOrDefault(fpe => fpe.GetFillPattern().IsSolidFill);

            return pattern?.Id ?? ElementId.InvalidElementId;
        }
    }
}
