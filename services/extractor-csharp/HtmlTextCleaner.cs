using System.Net;
using System.Text;
using System.Text.RegularExpressions;

internal static class HtmlTextCleaner
{
    internal const string TableStartMarker = "[TABLE]";
    internal const string TableEndMarker = "[/TABLE]";

    private static readonly Regex ScriptOrStyle = new(
        @"<(script|style)\b[^>]*>[\s\S]*?</\1>",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex HiddenIxHeader = new(
        @"<ix:header\b[\s\S]*?</ix:header>",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    // Innermost table: no nested <table> before the first </table>.
    private static readonly Regex TableBlock = new(
        @"<table\b[^>]*>(?:(?!<table\b)[\s\S])*?</table>",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex TableRow = new(
        @"<tr\b[^>]*>(?<inner>[\s\S]*?)</tr>",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex TableCell = new(
        @"<(?<tag>td|th)\b(?<attrs>[^>]*?)(?:\s*/>|>(?<inner>[\s\S]*?)</\k<tag>>)",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex BlockTag = new(
        @"</?(p|div|br|tr|h[1-6]|li|ul|ol|table|thead|tbody|section|article|header|footer|blockquote|pre)[^>]*>",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex AnyTag = new(@"<[^>]+>", RegexOptions.Compiled);

    private static readonly Regex HorizontalSpace = new(@"[ \t\f\v\u00A0]+", RegexOptions.Compiled);

    private static readonly Regex ExcessNewlines = new(@"\n{3,}", RegexOptions.Compiled);

    private static readonly Regex SmartApostrophes = new(
        "[\u2018\u2019\u201A\u201B\u2032\u2035]",
        RegexOptions.Compiled);

    private static readonly Regex SmartQuotes = new(
        "[\u201C\u201D\u201E\u201F\u00AB\u00BB]",
        RegexOptions.Compiled);

    private static readonly Regex YearToken = new(@"^(19|20)\d{2}$", RegexOptions.Compiled);

    private static readonly Regex NumericToken = new(
        @"^-?\(?[\d,]+(?:\.\d+)?\)?$",
        RegexOptions.Compiled);

    private const int LayoutCellCharLimit = 220;

    public static string ToText(string html)
    {
        if (string.IsNullOrWhiteSpace(html))
            return string.Empty;

        var text = ScriptOrStyle.Replace(html, " ");
        text = HiddenIxHeader.Replace(text, " ");
        text = WebUtility.HtmlDecode(text);
        text = NormalizeQuotes(text);
        text = ReplaceTables(text);
        text = FlattenTags(text);
        return NormalizeWhitespace(text);
    }

    private static string ReplaceTables(string html)
    {
        var context = new TableConvertContext();
        var previous = html;
        for (var pass = 0; pass < 8; pass++)
        {
            var replaced = TableBlock.Replace(previous, match => ConvertTable(match.Value, context));
            if (replaced == previous)
                return replaced;
            previous = replaced;
        }

        return previous;
    }

    private static string ConvertTable(string tableHtml, TableConvertContext context)
    {
        var rows = ParseTableRows(tableHtml);
        if (rows.Count == 0)
            return "\n";

        if (IsLayoutTable(rows))
            return FlattenTags(tableHtml);

        var lines = new List<string>();
        var headers = context.LastHeaders;
        var capturedHeader = false;

        foreach (var row in rows)
        {
            if (IsColumnHeaderRow(row))
            {
                headers = row;
                capturedHeader = true;
                continue;
            }

            if (row.Count == 1)
            {
                lines.Add(row[0]);
                continue;
            }

            var label = row[0];
            var values = row.Skip(1).ToList();
            var aligned = AlignHeaders(headers, values.Count);
            if (aligned is not null)
            {
                var parts = aligned.Zip(values, (header, value) => $"{header} {value}");
                lines.Add($"{label}: {string.Join("; ", parts)}");
            }
            else
            {
                lines.Add($"{label}: {string.Join("; ", values)}");
            }
        }

        if (lines.Count == 0)
            return "\n";

        if (capturedHeader)
            context.LastHeaders = headers;

        var builder = new StringBuilder();
        builder.Append("\n\n").Append(TableStartMarker).Append('\n');
        builder.AppendJoin('\n', lines);
        builder.Append('\n').Append(TableEndMarker).Append("\n\n");
        return builder.ToString();
    }

    private static List<List<string>> ParseTableRows(string tableHtml)
    {
        var rows = new List<List<string>>();
        foreach (Match rowMatch in TableRow.Matches(tableHtml))
        {
            var tokens = new List<string>();
            foreach (Match cellMatch in TableCell.Matches(rowMatch.Groups["inner"].Value))
            {
                var text = CellText(cellMatch.Groups["inner"].Value);
                if (text.Length > 0)
                    tokens.Add(text);
            }

            var merged = MergeTokens(tokens);
            if (merged.Count > 0)
                rows.Add(merged);
        }

        return rows;
    }

    private static string CellText(string? inner)
    {
        if (string.IsNullOrWhiteSpace(inner))
            return string.Empty;

        var text = AnyTag.Replace(inner, " ");
        text = HorizontalSpace.Replace(text, " ");
        return text.Trim();
    }

    private static List<string> MergeTokens(List<string> tokens)
    {
        var merged = new List<string>();
        for (var i = 0; i < tokens.Count; i++)
        {
            var current = tokens[i];
            var next = i + 1 < tokens.Count ? tokens[i + 1] : null;

            if (IsCurrencyPrefix(current) && next is not null && (IsNumericToken(next) || IsDash(next)))
            {
                merged.Add("$" + next);
                i++;
                continue;
            }

            if (next == "%" && (IsNumericToken(current) || IsDash(current) || current.EndsWith(')')))
            {
                merged.Add(current + "%");
                i++;
                continue;
            }

            merged.Add(current);
        }

        return merged;
    }

    private static bool IsLayoutTable(List<List<string>> rows) =>
        rows.Any(row => row.Any(cell => cell.Length > LayoutCellCharLimit));

    private static bool IsColumnHeaderRow(List<string> row)
    {
        if (row.Count < 2)
            return false;
        return !row.Any(IsAmountToken);
    }

    private static IReadOnlyList<string>? AlignHeaders(IReadOnlyList<string>? headers, int valueCount)
    {
        if (headers is null || headers.Count == 0)
            return null;
        if (headers.Count == valueCount)
            return headers;
        if (headers.Count - 1 == valueCount)
            return headers.Skip(1).ToList();

        var withoutChange = headers.Where(h => !IsChangeHeader(h)).ToList();
        if (withoutChange.Count == valueCount)
            return withoutChange;
        if (withoutChange.Count - 1 == valueCount)
            return withoutChange.Skip(1).ToList();

        return null;
    }

    private static bool IsChangeHeader(string header) =>
        header.Equals("Change", StringComparison.OrdinalIgnoreCase) ||
        header.Equals("Chg", StringComparison.OrdinalIgnoreCase) ||
        header.Equals("% Change", StringComparison.OrdinalIgnoreCase);

    private static bool IsAmountToken(string token)
    {
        if (YearToken.IsMatch(token))
            return false;
        if (token is "$" or "%" || IsDash(token) || token.StartsWith('$') || token.EndsWith('%'))
            return true;
        return NumericToken.IsMatch(token);
    }

    private static bool IsNumericToken(string token) => NumericToken.IsMatch(token);

    private static bool IsCurrencyPrefix(string token) =>
        token is "$" or "US$" or "USD";

    private static bool IsDash(string token) =>
        token is "-" or "—" or "–" or "−" or "―";

    private static string FlattenTags(string html)
    {
        var text = BlockTag.Replace(html, "\n");
        text = AnyTag.Replace(text, " ");
        return text;
    }

    private static string NormalizeWhitespace(string text)
    {
        text = HorizontalSpace.Replace(text, " ");
        text = Regex.Replace(text, @" *\n *", "\n");
        text = ExcessNewlines.Replace(text, "\n\n");
        return text.Trim();
    }

    private static string NormalizeQuotes(string text)
    {
        text = SmartApostrophes.Replace(text, "'");
        text = SmartQuotes.Replace(text, "\"");
        return text;
    }

    private sealed class TableConvertContext
    {
        public IReadOnlyList<string>? LastHeaders { get; set; }
    }
}
