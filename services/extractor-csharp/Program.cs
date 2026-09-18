using System.Diagnostics.CodeAnalysis;
using System.Text.Json;
using System.Text.RegularExpressions;

return AppEntry.Run(args);

public static class AppEntry
{
    public static int Run(string[] args)
    {
        var argsMap = ParseArgs(args);
        if (!argsMap.TryGetValue("input", out var inputDir) ||
            !argsMap.TryGetValue("output", out var outputDir) ||
            !argsMap.TryGetValue("report", out var reportPath))
        {
            Console.Error.WriteLine("Usage: --input <dir> --output <dir> --report <path>");
            return 2;
        }

        Directory.CreateDirectory(outputDir);
        var htmlFiles = Directory.GetFiles(inputDir, "*.html", SearchOption.TopDirectoryOnly)
            .Concat(Directory.GetFiles(inputDir, "*.htm", SearchOption.TopDirectoryOnly))
            .Distinct(StringComparer.OrdinalIgnoreCase)
            .OrderBy(path => path, StringComparer.OrdinalIgnoreCase)
            .ToArray();
        var warnings = new List<string>();
        var filesProcessed = 0;

        foreach (var file in htmlFiles)
        {
            var html = File.ReadAllText(file);
            var docId = Path.GetFileNameWithoutExtension(file);
            var extraction = ExtractSections(html);
            var sections = extraction.Sections
                .Select(section => section with { Text = HtmlTextCleaner.ToText(section.Text) })
                .Where(section => section.Text.Length > 0)
                .ToList();
            var fields = ExtractFields(HtmlTextCleaner.ToText(html));
            var validationWarnings = ValidateExtraction(sections, fields);
            var status = validationWarnings.Count == 0 ? "valid" : "partially_valid";

            warnings.AddRange(validationWarnings.Select(w => $"{docId}: {w}"));

            var result = new ExtractionResult(
                docId,
                file,
                sections,
                fields,
                status,
                validationWarnings,
                extraction.RegexMatches
            );
            var json = JsonSerializer.Serialize(
                result,
                new JsonSerializerOptions
                {
                    WriteIndented = true,
                    PropertyNamingPolicy = JsonNamingPolicy.CamelCase
                }
            );
            File.WriteAllText(Path.Combine(outputDir, $"{docId}.json"), json);
            filesProcessed++;
        }

        var report = JsonSerializer.Serialize(
            new { status = "completed", files_processed = filesProcessed, warnings },
            new JsonSerializerOptions
            {
                WriteIndented = true,
                PropertyNamingPolicy = JsonNamingPolicy.CamelCase
            }
        );
        File.WriteAllText(reportPath, report);
        Console.WriteLine($"Processed {filesProcessed} files");
        return 0;
    }

    private static Dictionary<string, string> ParseArgs(string[] args)
    {
        var result = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        for (var i = 0; i < args.Length - 1; i += 2)
        {
            var key = args[i].TrimStart('-');
            var value = args[i + 1];
            result[key] = value;
        }
        return result;
    }

    private static ExtractionSectionsResult ExtractSections(string html)
    {
        var tocBounds = FindTocBounds(html);
        var sectionRules = new[]
        {
            Section("Business", @"(?<!8220;)ITEM([\s&#;]|160)+1\.((?(?=<)<[^>]*>))*([\s&#;]|160)*BUSINESS(?<body>[\s\S]{100,}?)(?=ITEM([\s&#;]|160)+1A\.|ITEM([\s&#;]|160)+2\.)"),
            Section("Risk Factors", @"(?<!8220;)ITEM([\s&#;]|160)+1A\.((?(?=<)<[^>]*>))*([\s&#;]|160)*RISK([\s&#;]|160)+FACTORS(?<body>[\s\S]{100,}?)(?=ITEM([\s&#;]|160)+1B\.|ITEM([\s&#;]|160)+2\.)"),
            Section("MD&A", @"(?<!8220;)ITEM([\s&#;]|160)+7\.((?(?=<)<[^>]*>))*([\s&#;]|160)*(?<body>MANAGEMENT(['’&#;]|(8217))+S([\s&#;]|160)+DISCUSSION([\s&#;]|160)+AND([\s&#;]|160)+ANALYSIS[\s\S]{100,}?)(?=ITEM([\s&#;]|160)+7A\.|ITEM([\s&#;]|160)+8\.)"),
            Section("Signatures", @"(?<!8220;)SIGNATURES")
        };

        var sections = new List<SectionResult>();
        var regexMatches = new List<RegexMatchDebug>();
        foreach (var rule in sectionRules)
        {
            var (signatureBody, signatureMatches) = rule.Name == "Signatures"
                ? ChooseSignatureMatch(html)
                : (null, null);
            if (signatureMatches is not null)
            {
                regexMatches.AddRange(signatureMatches);
                if (signatureBody is not null)
                    sections.Add(new SectionResult(rule.Name, signatureBody));
                continue;
            }

            var (chosen, matches) = ChooseBodyMatch(html, rule.Name, rule.Pattern, tocBounds);

            regexMatches.AddRange(matches);

            if (chosen is not null)
            {
                sections.Add(new SectionResult(rule.Name, chosen.Groups["body"].Value));
            }
        }

        return new ExtractionSectionsResult(sections, regexMatches);
    }

    private const int SignaturesPursuantLookahead = 2000;

    private static readonly Regex SignaturesHeadingRegex = new(
        @"(?<!8220;)SIGNATURES",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static readonly Regex PursuantAfterHeadingRegex = new(
        @"((?(?=<)<[^>]*>))*[\s&#;\d]*Pursuant",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static (string? Body, List<RegexMatchDebug> Matches) ChooseSignatureMatch(string html)
    {
        var debugMatches = new List<RegexMatchDebug>();
        string? chosenBody = null;
        var bestCleanedLength = -1;
        var bestMatchIndex = -1;
        var matchIndex = 0;

        foreach (Match heading in SignaturesHeadingRegex.Matches(html).Cast<Match>())
        {
            var afterHeading = html[(heading.Index + heading.Length)..];
            var lookahead = afterHeading.Length <= SignaturesPursuantLookahead
                ? afterHeading
                : afterHeading[..SignaturesPursuantLookahead];
            var pursuantMatch = PursuantAfterHeadingRegex.Match(lookahead);
            var hasPursuant = pursuantMatch.Success;

            string bodyRaw;
            if (hasPursuant)
            {
                var matchStart = heading.Index + heading.Length + pursuantMatch.Index;
                var pursuantOffset = pursuantMatch.Value.IndexOf("Pursuant", StringComparison.OrdinalIgnoreCase);
                bodyRaw = html[(matchStart + pursuantOffset)..];
            }
            else
            {
                bodyRaw = afterHeading;
            }

            var cleaned = HtmlTextCleaner.ToText(bodyRaw);
            string? skippedReason = null;

            if (!hasPursuant)
            {
                skippedReason = "missing_pursuant_after_heading";
            }
            else if (cleaned.Length > bestCleanedLength)
            {
                if (bestMatchIndex >= 0)
                {
                    var previousBest = debugMatches[bestMatchIndex];
                    debugMatches[bestMatchIndex] = previousBest with
                    {
                        SkippedReason = "shorter_valid_match",
                        Selected = false
                    };
                }

                chosenBody = bodyRaw;
                bestCleanedLength = cleaned.Length;
                bestMatchIndex = matchIndex;
            }
            else
            {
                skippedReason = "shorter_valid_match";
            }

            debugMatches.Add(new RegexMatchDebug(
                SectionName: "Signatures",
                MatchIndex: matchIndex,
                StartIndex: heading.Index,
                EndIndex: heading.Index + heading.Length + (hasPursuant ? pursuantMatch.Index + pursuantMatch.Length : 0),
                InToc: false,
                LooksLikeTocFragment: LooksLikeTocFragment(cleaned),
                RawBodyLength: bodyRaw.Length,
                CleanedBodyLength: cleaned.Length,
                Selected: false,
                SkippedReason: skippedReason,
                Preview: PreviewText(cleaned)));

            matchIndex++;
        }

        if (bestMatchIndex >= 0)
        {
            var selected = debugMatches[bestMatchIndex];
            debugMatches[bestMatchIndex] = selected with
            {
                Selected = true,
                SkippedReason = null
            };
        }

        return (chosenBody, debugMatches);
    }

    private static (Match? Chosen, List<RegexMatchDebug> Matches) ChooseBodyMatch(
        string html,
        string sectionName,
        string pattern,
        (int Start, int End)? tocBounds)
    {
        var debugMatches = new List<RegexMatchDebug>();
        Match? chosen = null;
        var bestCleanedLength = -1;
        var bestMatchIndex = -1;
        var matchIndex = 0;

        foreach (var match in Regex.Matches(html, pattern, RegexOptions.IgnoreCase).Cast<Match>())
        {
            if (!match.Success)
                continue;

            var inToc = tocBounds is not null && IsInsideBounds(match.Index, tocBounds.Value);
            var cleaned = HtmlTextCleaner.ToText(match.Groups["body"].Value);
            var looksLikeToc = LooksLikeTocFragment(cleaned);
            string? skippedReason = null;

            if (inToc)
            {
                skippedReason = "inside_toc_bounds";
            }
            else if (cleaned.Length > bestCleanedLength)
            {
                if (bestMatchIndex >= 0)
                {
                    var previousBest = debugMatches[bestMatchIndex];
                    debugMatches[bestMatchIndex] = previousBest with
                    {
                        SkippedReason = "shorter_non_toc_match"
                    };
                }

                chosen = match;
                bestCleanedLength = cleaned.Length;
                bestMatchIndex = matchIndex;
            }
            else
            {
                skippedReason = "shorter_non_toc_match";
            }

            debugMatches.Add(new RegexMatchDebug(
                SectionName: sectionName,
                MatchIndex: matchIndex,
                StartIndex: match.Index,
                EndIndex: match.Index + match.Length,
                InToc: inToc,
                LooksLikeTocFragment: looksLikeToc,
                RawBodyLength: match.Groups["body"].Value.Length,
                CleanedBodyLength: cleaned.Length,
                Selected: false,
                SkippedReason: skippedReason,
                Preview: PreviewText(cleaned)));

            matchIndex++;
        }

        if (bestMatchIndex >= 0)
        {
            var selected = debugMatches[bestMatchIndex];
            debugMatches[bestMatchIndex] = selected with
            {
                Selected = true,
                SkippedReason = null
            };
        }

        return (chosen, debugMatches);
    }

    private static string PreviewText(string text, int limit = 180) =>
        text.Length <= limit ? text : text[..limit] + "...";

    private const int TocBodyHeadingLookback = 2000;

    private static readonly Regex Item1BusinessHeadingRegex = new(
        @"ITEM([\s&#;]|160)+1\.((?(?=<)<[^>]*>))*([\s&#;]|160)*BUSINESS",
        RegexOptions.IgnoreCase | RegexOptions.Compiled);

    private static (int Start, int End)? FindTocBounds(string html)
    {
        var tocStart = Regex.Match(html, @"TABLE\s+OF\s+CONTENTS", RegexOptions.IgnoreCase);
        if (!tocStart.Success)
            return null;

        var afterToc = html[(tocStart.Index + tocStart.Length)..];

        // Body often begins right after this phrase following the TOC block.
        var annualReportAnchor = Regex.Match(
            afterToc,
            @"This\s+Annual\s+Report\s+on\s+Form\s+10-K",
            RegexOptions.IgnoreCase);
        if (annualReportAnchor.Success)
        {
            var annualReportAbs = tocStart.Index + tocStart.Length + annualReportAnchor.Index;
            var lookbackStart = Math.Max(tocStart.Index + tocStart.Length, annualReportAbs - TocBodyHeadingLookback);
            var precedingRange = html[lookbackStart..annualReportAbs];
            Match? item1Business = null;
            foreach (Match match in Item1BusinessHeadingRegex.Matches(precedingRange))
                item1Business = match;

            // When Item 1. Business immediately precedes the annual-report phrase, that
            // marks the body start (e.g. AMZN) — not the TOC end. End the TOC there so
            // we do not treat the real Business section as inside the TOC window.
            var end = item1Business is not null
                ? lookbackStart + item1Business.Index
                : annualReportAbs;

            if (end > tocStart.Index)
                return (tocStart.Index, end);
        }

        // Secondary anchor: first "Part I ... Item 1" after TOC.
        var bodyAnchor = Regex.Match(
            afterToc,
            @"PART\s+I[\s\S]{0,2000}?ITEM\s+1\.",
            RegexOptions.IgnoreCase);
        if (bodyAnchor.Success)
        {
            var end = tocStart.Index + tocStart.Length + bodyAnchor.Index;
            if (end > tocStart.Index)
                return (tocStart.Index, end);
        }

        // Fallback: small window after TOC start (not a large doc prefix).
        var fallbackEnd = Math.Min(html.Length, tocStart.Index + 10_000);
        return (tocStart.Index, fallbackEnd);
    }

    private static bool IsInsideBounds(int index, (int Start, int End) bounds) =>
        index >= bounds.Start && index < bounds.End;

    private static bool LooksLikeTocFragment(string text)
    {
        if (text.Length < 200)
            return true;
        return false;
    }

    private static Dictionary<string, string> ExtractFields(string html)
    {
        var fields = new Dictionary<string, string>();
        var periodMatch = MatchIgnoreCase(
            html,
            @"for\s+the\s+fiscal\s+year\s+ended\s+(?(?=<)<[^>]*>)*(?<date>[A-Za-z]+([\s&#;]|160)+\d{1,2}(?(?=<)<[^>]*>)*\s*,\s*\d{4})");
        if (periodMatch.Success)
            AddField(fields, "fiscal_year_ended", NormalizeDate(periodMatch.Groups["date"].Value));

        var companyMatch = MatchIgnoreCase(html, @"(?<company>[A-Za-z0-9,\.\-&\s]{2,80})(?(?=<)<[^>]*>)*\s*\(?Exact\s+name\s+of\s+registrant\s+as\s+specified\s+in\s+its\s+charter");
        if (companyMatch.Success)
            AddField(fields, "company_name", LastNonEmptyLine(companyMatch.Groups["company"].Value));

        var filedMatch = MatchIgnoreCase(html, @"Commission\s+file\s+(number|no\.?)([\s&#;:]|160)+(?(?=<)<[^>]*>)*(?<value>[\d\-]+)");
        if (filedMatch.Success)
            AddField(fields, "commission_file_number", filedMatch.Groups["value"].Value);

        return fields;
    }

    private static List<string> ValidateExtraction(List<SectionResult> sections, Dictionary<string, string> fields)
    {
        var warnings = new List<string>();
        var requiredSections = new[] { "Business", "Risk Factors", "MD&A" };
        foreach (var section in requiredSections)
        {
            if (!sections.Any(s => s.Name == section))
                warnings.Add($"Missing required section: {section}");
        }

        var requiredFields = new[] { "fiscal_year_ended", "company_name" };
        foreach (var field in requiredFields)
        {
            if (!fields.ContainsKey(field))
                warnings.Add($"Missing required field: {field}");
        }

        return warnings;
    }

    private static string NormalizeDate(string value)
    {
        var cleaned = Regex.Replace(value, @"\s+", " ").Trim();
        return Regex.Replace(cleaned, @"\s+,", ",");
    }

    private static string LastNonEmptyLine(string value)
    {
        var lines = value.Split('\n', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        return lines.Length == 0 ? value.Trim() : lines[^1];
    }

    private static void AddField(Dictionary<string, string> fields, string name, string value)
    {
        var cleaned = value.Trim();
        if (cleaned.Length > 0)
            fields[name] = cleaned;
    }

    private static (string Name, string Pattern) Section(
        string name,
        [StringSyntax(StringSyntaxAttribute.Regex)] string pattern) => (name, pattern);

    private static Match MatchIgnoreCase(
        string input,
        [StringSyntax(StringSyntaxAttribute.Regex)] string pattern) =>
        Regex.Match(input, pattern, RegexOptions.IgnoreCase);

    private record SectionResult(string Name, string Text);
    private record RegexMatchDebug(
        string SectionName,
        int MatchIndex,
        int StartIndex,
        int EndIndex,
        bool InToc,
        bool LooksLikeTocFragment,
        int RawBodyLength,
        int CleanedBodyLength,
        bool Selected,
        string? SkippedReason,
        string Preview
    );
    private record ExtractionSectionsResult(
        List<SectionResult> Sections,
        List<RegexMatchDebug> RegexMatches
    );
    private record ExtractionResult(
        string DocumentId,
        string SourcePath,
        List<SectionResult> Sections,
        Dictionary<string, string> Fields,
        string ValidationStatus,
        List<string> Warnings,
        List<RegexMatchDebug> RegexMatches
    );
}
