using Autodesk.Revit.UI;
using Autodesk.Revit.DB;
using System;

namespace Aura.Revit.Services
{
    public class RevitExternalRunner : IExternalEventHandler
    {
        private Action<UIApplication> _currentTask;
        private readonly ExternalEvent _externalEvent;

        public RevitExternalRunner()
        {
            // needs to be instantiated on the main revit thread
            _externalEvent = ExternalEvent.Create(this);
        }

        public void Run(Action<UIApplication> task)
        {
            _currentTask = task;
            _externalEvent.Raise();
        }

        public void Execute(UIApplication app)
        {
            if (_currentTask == null) return;

            try
            {
                _currentTask.Invoke(app);
            }
            catch (Exception ex)
            {
                // fixme: implement proper silent logging instead of TaskDialog
                TaskDialog.Show("Aura Core Error", $"Execution failed: {ex.Message}");
            }
            finally
            {
                _currentTask = null;
            }
        }

        public string GetName() => "Aura_Async_Runner";
    }
}