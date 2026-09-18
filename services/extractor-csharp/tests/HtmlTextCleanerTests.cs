using Xunit;

public class HtmlTextCleanerTests
{
    [Fact]
    public void GrossMarginTable_LinearizesYearsWithValues()
    {
        var html = """
            <p>were as follows (dollars in millions):</p>
            <table>
              <tr><td></td><td colspan="3">2024</td><td colspan="3">2023</td><td colspan="3">2022</td></tr>
              <tr><td colspan="3">Gross margin:</td></tr>
              <tr>
                <td>Products</td>
                <td>$</td><td>109,633</td>
                <td>$</td><td>108,803</td>
                <td>$</td><td>114,728</td>
              </tr>
              <tr>
                <td>Services</td>
                <td>71,050</td>
                <td>60,345</td>
                <td>56,054</td>
              </tr>
              <tr>
                <td>Total gross margin</td>
                <td>$</td><td>180,683</td>
                <td>$</td><td>169,148</td>
                <td>$</td><td>170,782</td>
              </tr>
            </table>
            """;

        var text = HtmlTextCleaner.ToText(html);

        Assert.Contains("[TABLE]", text);
        Assert.Contains("[/TABLE]", text);
        Assert.Contains("Products: 2024 $109,633; 2023 $108,803; 2022 $114,728", text);
        Assert.Contains("Services: 2024 71,050; 2023 60,345; 2022 56,054", text);
        Assert.Contains("Total gross margin: 2024 $180,683; 2023 $169,148; 2022 $170,782", text);
        Assert.Contains("Gross margin:", text);
    }

    [Fact]
    public void ContinuationTable_ReusesPriorYearHeaders()
    {
        var html = """
            <table>
              <tr><td>2024</td><td>2023</td><td>2022</td></tr>
              <tr><td>Products</td><td>$</td><td>109,633</td><td>$</td><td>108,803</td><td>$</td><td>114,728</td></tr>
            </table>
            <table>
              <tr><td colspan="3">Gross margin percentage:</td></tr>
              <tr>
                <td>Products</td>
                <td>37.2</td><td>%</td>
                <td>36.5</td><td>%</td>
                <td>36.3</td><td>%</td>
              </tr>
              <tr>
                <td>Services</td>
                <td>73.9</td><td>%</td>
                <td>70.8</td><td>%</td>
                <td>71.7</td><td>%</td>
              </tr>
            </table>
            """;

        var text = HtmlTextCleaner.ToText(html);

        Assert.Contains("Products: 2024 37.2%; 2023 36.5%; 2022 36.3%", text);
        Assert.Contains("Services: 2024 73.9%; 2023 70.8%; 2022 71.7%", text);
        Assert.Equal(2, CountTables(text));
    }

    [Fact]
    public void ChangeColumns_PairWhenCountsMatch_AndDropChangeForShorterRows()
    {
        var html = """
            <table>
              <tr>
                <td>2024</td><td>Change</td>
                <td>2023</td><td>Change</td>
                <td>2022</td>
              </tr>
              <tr>
                <td>Research and development</td>
                <td>$</td><td>31,370</td><td>5</td><td>%</td>
                <td>$</td><td>29,915</td><td>14</td><td>%</td>
                <td>$</td><td>26,251</td>
              </tr>
              <tr>
                <td>Percentage of total net sales</td>
                <td>8</td><td>%</td>
                <td>8</td><td>%</td>
                <td>7</td><td>%</td>
              </tr>
            </table>
            """;

        var text = HtmlTextCleaner.ToText(html);

        Assert.Contains(
            "Research and development: 2024 $31,370; Change 5%; 2023 $29,915; Change 14%; 2022 $26,251",
            text);
        Assert.Contains("Percentage of total net sales: 2024 8%; 2023 8%; 2022 7%", text);
    }

    [Fact]
    public void EmDashPercent_MergesIntoValue()
    {
        var html = """
            <table>
              <tr><td>2024</td><td>Change</td><td>2023</td><td>Change</td><td>2022</td></tr>
              <tr>
                <td>iPhone</td>
                <td>$</td><td>201,183</td><td>—</td><td>%</td>
                <td>$</td><td>200,583</td><td>(2)</td><td>%</td>
                <td>$</td><td>205,489</td>
              </tr>
            </table>
            """;

        var text = HtmlTextCleaner.ToText(html);

        Assert.Contains("iPhone: 2024 $201,183; Change —%; 2023 $200,583; Change (2)%; 2022 $205,489", text);
    }

    [Fact]
    public void LayoutTable_FlattenedWithoutMarkers()
    {
        var longCell = new string('x', 240);
        var html = $"<table><tr><td>How We Addressed the Matter in Our Audit</td><td>{longCell}</td></tr></table>";

        var text = HtmlTextCleaner.ToText(html);

        Assert.DoesNotContain("[TABLE]", text);
        Assert.Contains("How We Addressed the Matter in Our Audit", text);
        Assert.Contains(longCell, text);
    }

    [Fact]
    public void EmptySpacerTable_Omitted()
    {
        var html = """<p>Before</p><table><tr><td style="width:1%"/><td style="width:1%"/></tr></table><p>After</p>""";

        var text = HtmlTextCleaner.ToText(html);

        Assert.DoesNotContain("[TABLE]", text);
        Assert.Contains("Before", text);
        Assert.Contains("After", text);
    }

    [Fact]
    public void SurroundingProse_IsPreserved()
    {
        var html = """
            <p>Operating expenses for 2024 were as follows (dollars in millions):</p>
            <table>
              <tr><td>2024</td><td>2023</td></tr>
              <tr><td>Research and development</td><td>$</td><td>31,370</td><td>$</td><td>29,915</td></tr>
            </table>
            <p>The growth in R&amp;D expense was driven by headcount.</p>
            """;

        var text = HtmlTextCleaner.ToText(html);

        Assert.StartsWith("Operating expenses", text);
        Assert.Contains("[TABLE]", text);
        Assert.Contains("Research and development: 2024 $31,370; 2023 $29,915", text);
        Assert.Contains("The growth in R&D expense was driven by headcount.", text);
    }

    private static int CountTables(string text)
    {
        var count = 0;
        var index = 0;
        while ((index = text.IndexOf("[TABLE]", index, StringComparison.Ordinal)) >= 0)
        {
            count++;
            index += "[TABLE]".Length;
        }

        return count;
    }
}
