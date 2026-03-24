using System;
using System.Text.Json;
using System.Globalization;
using Autodesk.Revit.DB;

namespace Aura.Revit.Utils
{
    public static class ParameterHandler
    {
        // expected JSON payload: { "elements": [ { "id": 12345, "parameters": { "Aura_Carbon": 45.2, "Aura_Material": "Timber" } } ] }
        public static int UpdateParametersFromJson(Document doc, string jsonPayload)
        {
            int updatedCount = 0;

            try
            {
                using (JsonDocument parsedJson = JsonDocument.Parse(jsonPayload))
                {
                    JsonElement root = parsedJson.RootElement;

                    if (!root.TryGetProperty("elements", out JsonElement elementsArray) || elementsArray.ValueKind != JsonValueKind.Array)
                        return 0;

                    foreach (JsonElement element in elementsArray.EnumerateArray())
                    {
                        if (element.TryGetProperty("id", out JsonElement idElement) &&
                            element.TryGetProperty("parameters", out JsonElement paramsElement))
                        {
                            long elemId = idElement.GetInt64();
                            Element revitElement = doc.GetElement(new ElementId(elemId));

                            if (revitElement == null) continue;

                            foreach (JsonProperty param in paramsElement.EnumerateObject())
                            {
                                string paramName = param.Name;
                                string paramValue = param.Value.ToString();

                                if (UpdateElementParameter(revitElement, paramName, paramValue))
                                {
                                    updatedCount++;
                                }
                            }
                        }
                    }
                }
            }
            catch
            {
                // fail silently for bulk operations
            }

            return updatedCount;
        }

        private static bool UpdateElementParameter(Element elem, string paramName, string value)
        {
            Parameter param = elem.LookupParameter(paramName);

            if (param == null || param.IsReadOnly) return false;

            try
            {
                switch (param.StorageType)
                {
                    case StorageType.String:
                        param.Set(value);
                        break;
                    case StorageType.Double:
                        // invariant culture to prevent dot/comma parsing errors 
                        if (double.TryParse(value, NumberStyles.Any, CultureInfo.InvariantCulture, out double doubleVal))
                            param.Set(doubleVal);
                        break;
                    case StorageType.Integer:
                        if (int.TryParse(value, out int intVal))
                            param.Set(intVal);
                        break;
                    case StorageType.ElementId:
                        if (long.TryParse(value, out long idVal))
                            param.Set(new ElementId(idVal));
                        break;
                    default:
                        return false;
                }
                return true;
            }
            catch
            {
                return false;
            }
        }
    }
}