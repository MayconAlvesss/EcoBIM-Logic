using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;
using Aura.Revit.Services;
using Aura.Revit.UI;
using System;

namespace Aura.Revit
{
    [Transaction(TransactionMode.Manual)]
    public class Command : IExternalCommand
    {
        // singleton-ish reference to prevent window duplication
        private static DashboardView? _dashboardWindow;

        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            try
            {
                if (_dashboardWindow == null || !_dashboardWindow.IsLoaded)
                {
                    var runner = new RevitExternalRunner();
                    var viewModel = new DashboardViewModel(runner);
                    
                    _dashboardWindow = new DashboardView(viewModel);
                    
                    // keep modeless so user can interact with the model
                    _dashboardWindow.Show(); 
                }
                else
                {
                    _dashboardWindow.Activate();
                }

                return Result.Succeeded;
            }
            catch (Exception ex)
            {
                message = ex.Message;
                return Result.Failed;
            }
        }
    }
}