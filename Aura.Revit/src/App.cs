using Autodesk.Revit.UI;
using System;
using System.Reflection;
using System.Windows.Media.Imaging;

namespace Aura.Revit
{
    public class App : IExternalApplication
    {
        public Result OnStartup(UIControlledApplication application)
        {
            try
            {
                string tabName = "Aura BIM";
                application.CreateRibbonTab(tabName);

                RibbonPanel panel = application.CreateRibbonPanel(tabName, "AI & LCA Sync");
                string assemblyPath = Assembly.GetExecutingAssembly().Location;

                // bind sync command to UI
                PushButtonData buttonData = new PushButtonData(
                    "btnAuraSync",
                    "Aura\nDashboard",
                    assemblyPath,
                    "Aura.Revit.Command" 
                )
                {
                    ToolTip = "Launches the model synchronization panel with the Aura AI API.",
                    // fixme: add actual icon resources later
                    // LargeImage = new BitmapImage(new Uri("pack://application:,,,/Aura.Revit;component/Resources/icon.png"))
                };

                panel.AddItem(buttonData);

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                Autodesk.Revit.UI.TaskDialog.Show("Aura Initialization Error", ex.Message);
                return Result.Failed;
            }
        }

        public Result OnShutdown(UIControlledApplication application)
        {
            return Result.Succeeded;
        }
    }
}