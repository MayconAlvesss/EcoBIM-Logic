using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;

namespace Aura.Revit.Services
{
    public class ApiClient
    {
        private readonly HttpClient _httpClient;
        
        // fixme: move to settings file or environment var before prod
        private const string API_URL = "http://localhost:8000/api/v1/sync/process-model";

        public ApiClient()
        {
            _httpClient = new HttpClient();
            _httpClient.Timeout = TimeSpan.FromSeconds(30);
        }

        public async Task<string> GetCarbonDataAsync()
        {
            try
            {
                // mock delay to simulate heavy LCA calculation
                await Task.Delay(1500); 

                HttpResponseMessage response = await _httpClient.GetAsync(API_URL);
                response.EnsureSuccessStatusCode();

                return await response.Content.ReadAsStringAsync();
            }
            catch (HttpRequestException ex)
            {
                // return string error instead of throwing to simplify UI binding
                return $"Error: API Unreachable. {ex.Message}";
            }
            catch (Exception ex)
            {
                return $"Error: {ex.Message}";
            }
        }
    }
}