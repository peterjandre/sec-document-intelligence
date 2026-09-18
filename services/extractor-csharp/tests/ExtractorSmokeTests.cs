using System.Diagnostics;
using Xunit;

public class ExtractorSmokeTests
{
    [Fact]
    public void CliProcessesSampleHtml()
    {
        var root = Path.GetFullPath(Path.Combine(AppContext.BaseDirectory, "..", "..", "..", ".."));
        var inputDir = Path.Combine(root, "fixtures");
        var outputDir = Path.Combine(Path.GetTempPath(), $"extractor-out-{Guid.NewGuid()}");
        var reportPath = Path.Combine(outputDir, "report.json");
        Directory.CreateDirectory(outputDir);

        var psi = new ProcessStartInfo
        {
            FileName = "dotnet",
            WorkingDirectory = root,
            Arguments = $"run --project extractor-csharp.csproj -- --input \"{inputDir}\" --output \"{outputDir}\" --report \"{reportPath}\"",
            RedirectStandardError = true,
            RedirectStandardOutput = true
        };
        using var process = Process.Start(psi);
        process!.WaitForExit();

        Assert.True(process.ExitCode == 0, process.StandardError.ReadToEnd());
        Assert.True(File.Exists(reportPath));
    }
}
