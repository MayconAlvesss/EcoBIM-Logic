using System;
using System.IO;
using System.Windows;
using Microsoft.Web.WebView2.Core;
using Aura.Revit.Services;
using Autodesk.Revit.DB;

namespace Aura.Revit.UI
{
    public partial class DashboardView : Window
    {
        private readonly DashboardViewModel _viewModel;

        public DashboardView(DashboardViewModel viewModel)
        {
            InitializeComponent();
            _viewModel = viewModel;
            DataContext = _viewModel;

            _viewModel.OnDataAggregated += ViewModel_OnDataAggregated;
            InitializeWebViewAsync();
        }

        private async void InitializeWebViewAsync()
        {
            var env = await CoreWebView2Environment.CreateAsync(null, Path.GetTempPath());
            await MainWebView.EnsureCoreWebView2Async(env);
            MainWebView.DefaultBackgroundColor = System.Drawing.Color.Transparent;

            // Locate the HTML file in the web/ folder relative to this DLL's physical deployed location.
            string assemblyDir = Path.GetDirectoryName(System.Reflection.Assembly.GetExecutingAssembly().Location) ?? AppDomain.CurrentDomain.BaseDirectory;
            string htmlPath = Path.Combine(assemblyDir, "web", "index.html");
            
            // Fallback for development structure
            if (!File.Exists(htmlPath))
            {
                htmlPath = Path.GetFullPath(Path.Combine(assemblyDir, @"..\..\..\..\web\index.html"));
            }

            MainWebView.CoreWebView2.Navigate(htmlPath);
            MainWebView.CoreWebView2.WebMessageReceived += CoreWebView2_WebMessageReceived;
        }

        private void ViewModel_OnDataAggregated(object? sender, string jsonPayload)
        {
            // Send the JSON payload to the JavaScript frontend
            System.Windows.Application.Current.Dispatcher.Invoke(() =>
            {
                MainWebView.CoreWebView2.PostWebMessageAsJson(jsonPayload);
            });
        }

        private void CoreWebView2_WebMessageReceived(object? sender, CoreWebView2WebMessageReceivedEventArgs e)
        {
            string msg = e.TryGetWebMessageAsString();
            if (msg == "APPLY_HEATMAP")
            {
                System.Diagnostics.Debug.WriteLine("[Aura] APPLY_HEATMAP received from WebView.");
            }
        }

        private void TitleBar_MouseLeftButtonDown(object sender, System.Windows.Input.MouseButtonEventArgs e)
        {
            if (e.LeftButton == System.Windows.Input.MouseButtonState.Pressed)
            {
                this.DragMove();
            }
        }

        private void CloseButton_Click(object sender, RoutedEventArgs e)
        {
            this.Close();
        }
    }
}