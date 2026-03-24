using Autodesk.Revit.UI;
using Autodesk.Revit.DB;
using System;
using System.Diagnostics;
using System.Threading.Tasks;

namespace Aura.Revit.Services
{
    /// <summary>
    /// Bridges the async WPF world with the synchronous Revit API thread.
    ///
    /// Revit requires that all API calls happen on its main UI thread.
    /// This handler registers as an IExternalEventHandler so Revit can invoke
    /// it safely. Two overloads are provided:
    ///
    ///   Run(Action)        — fire-and-forget, for write operations already inside a transaction.
    ///   RunAsync<T>(Func)  — returns a Task<T> so ViewModel async methods can await the result.
    ///
    /// Both overloads share the same underlying ExternalEvent instance.
    /// Concurrent calls are prevented by the IsBusy flag on the ViewModel.
    /// </summary>
    public class RevitExternalRunner : IExternalEventHandler
    {
        private Action<UIApplication>? _currentTask;
        private readonly ExternalEvent _externalEvent;

        public RevitExternalRunner()
        {
            // ExternalEvent.Create must be called on the Revit main thread.
            // Instantiate this class from App.OnStartup or from a Revit command, never from a background thread.
            _externalEvent = ExternalEvent.Create(this);
        }

        /// <summary>
        /// Queues a fire-and-forget action to be executed on the Revit main thread.
        /// Errors are logged to the Debug output rather than thrown, to avoid
        /// blocking modal dialogs inside a modeless add-in window.
        /// </summary>
        public void Run(Action<UIApplication> task)
        {
            _currentTask = task;
            _externalEvent.Raise();
        }

        /// <summary>
        /// Queues a data-gathering function to run on the Revit main thread and
        /// returns a Task<T> that resolves once the ExternalEvent has fired.
        ///
        /// Usage (from an async ViewModel method):
        ///   var payload = await _revitRunner.RunAsync(app => BuildPayload(app));
        ///
        /// The continuation after the await is posted back to the WPF
        /// SynchronizationContext captured at the point of the call, so
        /// bound properties can be updated directly without Dispatcher.Invoke.
        /// </summary>
        public Task<T> RunAsync<T>(Func<UIApplication, T> dataTask)
        {
            // RunContinuationsAsynchronously ensures the TCS continuation does not
            // run inline on the Revit event thread, which could deadlock WPF.
            var tcs = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);

            _currentTask = app =>
            {
                try
                {
                    T result = dataTask(app);
                    tcs.SetResult(result);
                }
                catch (Exception ex)
                {
                    // Propagate the exception into the awaiting Task chain
                    // rather than catching it silently here.
                    tcs.SetException(ex);
                }
            };

            _externalEvent.Raise();
            return tcs.Task;
        }

        // ── IExternalEventHandler implementation ───────────────────────────────

        public void Execute(UIApplication app)
        {
            if (_currentTask == null) return;

            try
            {
                _currentTask.Invoke(app);
            }
            catch (Exception ex)
            {
                // This catch handles the rare case where _currentTask itself
                // throws synchronously before any TCS is involved (i.e. the
                // plain Run() overload, which does not use a TCS).
                Debug.WriteLine($"[Aura] RevitExternalRunner caught an exception: {ex.Message}");
                Debug.WriteLine(ex.StackTrace);
            }
            finally
            {
                _currentTask = null;
            }
        }

        public string GetName() => "Aura_Async_Runner";
    }
}
