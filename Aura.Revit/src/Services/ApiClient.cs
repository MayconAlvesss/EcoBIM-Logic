using System;
using System.Net.Http;
using System.Net.Http.Headers;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using Aura.Revit.Models;

namespace Aura.Revit.Services
{
    public class ApiClient
    {
        private readonly HttpClient _httpClient;

        // Read URL and API key from environment variables so they can be
        // changed per deployment without recompiling the add-in.
        // Fallback to localhost defaults for local development.
        private readonly string _apiUrl;
        private readonly string _apiKey;

        private const string DEFAULT_API_URL = "http://localhost:8000/api/v1/sync/process-model";
        private const string DEFAULT_API_KEY = "aura-dev-key-super-secret";

        public ApiClient()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(30);

            _apiUrl = Environment.GetEnvironmentVariable("AURA_API_URL") ?? DEFAULT_API_URL;
            _apiKey = Environment.GetEnvironmentVariable("AURA_API_KEY") ?? DEFAULT_API_KEY;

            // Set the auth key as a default header so every request includes it automatically
            _httpClient.DefaultRequestHeaders.Add("X-Aura-API-Key", _apiKey);
        }

        public async Task<string> PostBimPayloadAsync(SyncPayload payload)
        {
            try
            {
                // Serialize the BIM sync payload to JSON
                string json = JsonSerializer.Serialize(payload);
                var content = new StringContent(json, Encoding.UTF8, "application/json");

                // The endpoint is POST-only — using GetAsync was causing HTTP 405
                HttpResponseMessage response = await _httpClient.PostAsync(_apiUrl, content);
                response.EnsureSuccessStatusCode();

                return await response.Content.ReadAsStringAsync();
            }
            catch (HttpRequestException ex)
            {
                // Return an error string instead of throwing so the ViewModel
                // can bind to it directly without an unhandled exception
                return $"Error: API Unreachable. {ex.Message}";
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}";
            }
        }
    }
}