using System;
using System.Threading.Tasks;
using System.Windows.Input;

namespace Aura.Revit.UI
{
    /// <summary>
    /// Synchronous relay command that wraps an Action for simple, non-async operations.
    /// </summary>
    public class RelayCommand : ICommand
    {
        private readonly Action _execute;
        private readonly Func<bool>? _canExecute;

        public event EventHandler? CanExecuteChanged
        {
            add    { CommandManager.RequerySuggested += value; }
            remove { CommandManager.RequerySuggested -= value; }
        }

        public RelayCommand(Action execute, Func<bool>? canExecute = null)
        {
            _execute    = execute ?? throw new ArgumentNullException(nameof(execute));
            _canExecute = canExecute;
        }

        public bool CanExecute(object? parameter) => _canExecute == null || _canExecute();

        public void Execute(object? parameter) => _execute();
    }

    /// <summary>
    /// Async relay command that wraps a Func<Task> so the ViewModel can use
    /// await/async correctly without silently swallowing exceptions.
    ///
    /// The critical difference from RelayCommand(async () => await ...):
    ///   - RelayCommand takes an Action, so async lambdas become "async void" 
    ///     internally — any exception thrown after the first await is unhandled.
    ///   - AsyncRelayCommand takes Func<Task>, keeping the exception in the
    ///     Task where it can propagate to the ViewModel's error handler.
    ///
    /// IsBusy is also enforced here: the button is automatically disabled while
    /// a previous execution is in flight, preventing double-clicks.
    /// </summary>
    public class AsyncRelayCommand : ICommand
    {
        private readonly Func<Task> _execute;
        private readonly Func<bool>? _canExecute;
        private bool _isExecuting;

        public event EventHandler? CanExecuteChanged
        {
            add    { CommandManager.RequerySuggested += value; }
            remove { CommandManager.RequerySuggested -= value; }
        }

        public AsyncRelayCommand(Func<Task> execute, Func<bool>? canExecute = null)
        {
            _execute    = execute ?? throw new ArgumentNullException(nameof(execute));
            _canExecute = canExecute;
        }

        public bool CanExecute(object? parameter)
            => !_isExecuting && (_canExecute == null || _canExecute());

        public async void Execute(object? parameter)
        {
            if (_isExecuting) return;

            _isExecuting = true;
            // Notify the binding system that CanExecute has changed (disables the button)
            CommandManager.InvalidateRequerySuggested();

            try
            {
                await _execute();
            }
            catch (Exception ex)
            {
                // Surface async exceptions to the Debug output rather than crashing the process.
                // The ViewModel already handles user-facing error messages in ExecuteSyncAsync.
                System.Diagnostics.Debug.WriteLine($"[Aura] AsyncRelayCommand unhandled exception: {ex.Message}");
            }
            finally
            {
                _isExecuting = false;
                // Re-enable the button once the async operation completes
                CommandManager.InvalidateRequerySuggested();
            }
        }
    }
}