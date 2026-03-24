using System.Windows;

namespace Aura.Revit
{
    /// <summary>
    /// Lógica de arranque para o modo de teste (Visualização independente)
    /// </summary>
    public partial class App : Application
    {
        // Este ficheiro precisa de existir para o WPF saber como inicializar
        // a classe definida no ficheiro App.xaml que tens no Canvas.
        // Podes deixá-lo vazio por agora, pois a StartupUri já está definida no XAML.
    }
}