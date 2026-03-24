using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Linq;
using System.Runtime.CompilerServices;
using System.Threading.Tasks;
using System.Windows.Input;
using Aura.Revit.Models;
using Aura.Revit.Services;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace Aura.Revit.UI
{
    public class DashboardViewModel : INotifyPropertyChanged
    {
        private const double CUBIC_FEET_TO_M3 = 0.0283168;
        
        private static readonly BuiltInCategory[] TARGET_CATEGORIES =
        {
            BuiltInCategory.OST_Walls, BuiltInCategory.OST_Floors,
            BuiltInCategory.OST_Roofs, BuiltInCategory.OST_StructuralColumns,
            BuiltInCategory.OST_StructuralFraming, BuiltInCategory.OST_StructuralFoundation,
        };

        private readonly ApiClient _apiClient;
        private readonly RevitExternalRunner _revitRunner;

        public event EventHandler<string>? OnDataAggregated;

        private string _statusMessage = "Ready — click Sync & Analyze.";
        public string StatusMessage
        {
            get => _statusMessage;
            set { _statusMessage = value; OnPropertyChanged(); }
        }

        private bool _isBusy;
        public bool IsBusy
        {
            get => _isBusy;
            set { _isBusy = value; OnPropertyChanged(); }
        }

        public ICommand SyncCommand { get; }
        public ICommand PreviewHeatmapCommand { get; }
        public ICommand ClearHeatmapCommand { get; }

        public DashboardViewModel(RevitExternalRunner revitRunner)
        {
            _apiClient   = new ApiClient();
            _revitRunner = revitRunner;
            SyncCommand           = new AsyncRelayCommand(ExecuteSyncAsync, () => !IsBusy);
            PreviewHeatmapCommand = new RelayCommand(ApplyCategoryPreview, () => !IsBusy);
            ClearHeatmapCommand   = new RelayCommand(ClearHeatmap, () => !IsBusy);
        }

        private void ClearHeatmap()
        {
            IsBusy = true;
            StatusMessage = "Clearing Overrides...";
            try
            {
                _revitRunner.Run(app =>
                {
                    var uiDoc = app.ActiveUIDocument;
                    HeatmapVisualizer.ClearAllOverrides(uiDoc.Document, uiDoc.ActiveView);
                });
                StatusMessage = "Overrides cleared. Model restored.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Clear failed: {ex.Message}";
            }
            finally { IsBusy = false; }
        }

        private AuraApiResponse? _lastParsedData;
        private SyncPayload?     _lastPayload;

        // ── Step 1: Category Preview (works WITHOUT API) ───────────────────────
        // Immediately colours elements so the user sees visual feedback on click.
        private void ApplyCategoryPreview()
        {
            IsBusy = true;
            StatusMessage = "Applying Category Preview...";
            try
            {
                int count = 0;
                _revitRunner.Run(app =>
                {
                    var uiDoc = app.ActiveUIDocument;
                    count = HeatmapVisualizer.ApplyCategoryFallback(uiDoc.Document, uiDoc.ActiveView);
                });
                StatusMessage = count > 0
                    ? $"Preview OK — {count} elements coloured by category."
                    : "Preview: 0 elements found. Is a 3D view active?";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Preview failed: {ex.Message}";
            }
            finally { IsBusy = false; }
        }

        // ── Step 2: Full Sync + WLCA heatmap ──────────────────────────────────
        private async Task ExecuteSyncAsync()
        {
            IsBusy = true;
            StatusMessage = "Scanning Elements...";

            // ── 2a. Apply instant category colours so user sees SOMETHING immediately
            try
            {
                _revitRunner.Run(app =>
                {
                    var uiDoc = app.ActiveUIDocument;
                    HeatmapVisualizer.ApplyCategoryFallback(uiDoc.Document, uiDoc.ActiveView);
                });
            }
            catch { /* non-critical */ }

            // ── 2b. Build the payload from Revit elements
            SyncPayload payload = await _revitRunner.RunAsync<SyncPayload>(app => BuildSyncPayload(app));
            _lastPayload = payload;

            if (payload.Elements.Count == 0)
            {
                StatusMessage = "No compatible elements found for LCA.";
                IsBusy = false; return;
            }

            // Publish element summary to WebView immediately (before API call)
            PublishPreviewToWebView(payload);

            StatusMessage = $"Sending {payload.Elements.Count} elements to WLCA Engine...";
            string responseJson = await _apiClient.PostBimPayloadAsync(payload);

            if (responseJson.StartsWith("Error"))
            {
                StatusMessage = $"API offline: {responseJson}";
                IsBusy = false; return;
            }

            StatusMessage = "Parsing WLCA results...";

            AuraApiResponse? parsedData = null;
            try
            {
                var result = await _revitRunner.RunAsync(app =>
                {
                    Document doc = app.ActiveUIDocument.Document;
                    using Transaction t = new(doc, "Aura: Write LCA Results");
                    t.Start();
                    var res = ParameterHandler.UpdateParametersFromJson(doc, responseJson);
                    t.Commit();
                    return res;
                });

                parsedData      = result.ParsedData;
                _lastParsedData = parsedData;
                StatusMessage   = $"Done — {result.UpdatedCount}/{payload.Elements.Count} elements with WLCA data.";
            }
            catch (Exception ex)
            {
                StatusMessage = $"Write-back error: {ex.Message}";
            }

            // ── 2c. Apply precision heatmap (overwrites the category preview)
            if (parsedData != null && parsedData.Elements.Count > 0)
            {
                try
                {
                    int coloured = await _revitRunner.RunAsync<int>(app =>
                    {
                        var uiDoc = app.ActiveUIDocument;
                        return HeatmapVisualizer.ApplyCarbonHeatmap(uiDoc.Document, uiDoc.ActiveView, parsedData);
                    });
                    StatusMessage += $", {coloured} elements coloured.";
                }
                catch (Exception ex)
                {
                    StatusMessage += $" (Heatmap: {ex.Message})";
                }

                // Send full data to WebView2
                string jsonForWebView = LcaAggregator.BuildWebPayload(
                    payload.ProjectId ?? "EcoBIM Project", parsedData, payload);
                OnDataAggregated?.Invoke(this, jsonForWebView);
            }

            IsBusy = false;
        }

        /// <summary>
        /// Sends a lightweight "element count + category summary" JSON to the WebView
        /// immediately after scanning — before the API responds — so the dashboard is
        /// never blank.
        /// </summary>
        private void PublishPreviewToWebView(SyncPayload payload)
        {
            if (payload.Elements.Count == 0) return;

            var groups = payload.Elements
                .GroupBy(e => NormaliseCategory(e.Category))
                .Select(g => new {
                    category = g.Key,
                    count    = g.Count(),
                    vol      = g.Sum(e => e.Volume)
                }).ToList();

            var preview = new
            {
                preview = true,
                project = payload.ProjectId,
                scanned = payload.Elements.Count,
                groups
            };

            string json = System.Text.Json.JsonSerializer.Serialize(preview);
            OnDataAggregated?.Invoke(this, json);
        }

        // ── Helpers ────────────────────────────────────────────────────────────

        private static SyncPayload BuildSyncPayload(UIApplication app)
        {
            UIDocument uidoc = app.ActiveUIDocument;
            Document   doc   = uidoc.Document;
            var elements = new List<ElementData>();

            foreach (BuiltInCategory category in TARGET_CATEGORIES)
            {
                var collected = new FilteredElementCollector(doc)
                    .OfCategory(category)
                    .WhereElementIsNotElementType()
                    .ToElements();

                foreach (Element elem in collected)
                {
                    Parameter? volParam = elem.get_Parameter(BuiltInParameter.HOST_VOLUME_COMPUTED);
                    double vol = volParam?.HasValue == true ? volParam.AsDouble() * CUBIC_FEET_TO_M3 : 0.0;
                    if (vol < 0.001) continue;

                    elements.Add(new ElementData
                    {
                        Id           = elem.Id.Value,
                        Category     = NormaliseCategory(elem.Category?.Name ?? category.ToString()),
                        Volume       = Math.Round(vol, 4),
                        MaterialName = GetPrimaryMaterialName(doc, elem)
                    });
                }
            }

            return new SyncPayload
            {
                ProjectId = $"AURA_{DateTime.UtcNow:yyyyMMdd}",
                Elements  = elements
            };
        }

        /// <summary>Map Revit category names (any language) to stable English keys.</summary>
        private static string NormaliseCategory(string? revitCat)
        {
            if (string.IsNullOrEmpty(revitCat)) return "Other";
            string lower = revitCat.ToLowerInvariant();
            if (lower.Contains("wall")   || lower.Contains("par"))  return "Walls";
            if (lower.Contains("floor")  || lower.Contains("piso")) return "Floors";
            if (lower.Contains("roof")   || lower.Contains("teto") || lower.Contains("cober")) return "Roofs";
            if (lower.Contains("column") || lower.Contains("pilar")) return "Columns";
            if (lower.Contains("fram")   || lower.Contains("viga") || lower.Contains("beam"))  return "Beams";
            if (lower.Contains("found")  || lower.Contains("fund")) return "Foundation";
            return revitCat;
        }

        private static string GetPrimaryMaterialName(Document doc, Element elem)
        {
            try
            {
                var matIds = elem.GetMaterialIds(false);
                if (matIds.Count > 0 && doc.GetElement(matIds.First()) is Material mat)
                    return mat.Name;
                Parameter? p = elem.get_Parameter(BuiltInParameter.SYMBOL_NAME_PARAM);
                return p?.AsString() ?? "Unknown";
            }
            catch { return "Unknown"; }
        }

        public event PropertyChangedEventHandler? PropertyChanged;
        protected void OnPropertyChanged([CallerMemberName] string? name = null)
            => PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(name));
    }
}
