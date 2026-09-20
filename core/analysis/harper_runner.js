import('harper.js').then(async m => {
  const binary = await import('../../node_modules/harper.js/dist/binaryInlined.js');
  const linter = new m.LocalLinter({ binary: binary.binaryInlined });
  await linter.setup();
  
  let buffer = '';
  process.stdin.on('data', chunk => { buffer += chunk; });
  process.stdin.on('end', async () => {
    try {
      const text = buffer;
      const lints = await linter.lint(text);
      const inner = await linter.inner;
      const results = [];
      for (const lint of lints) {
        const span = lint.span();
        const suggestions = lint.suggestions(inner);
        const replacements = suggestions.map(s => {
          try { return s.get_replacement_text(inner); } catch(e) { return null; }
        }).filter(Boolean);
        
        results.push({
          message: lint.message(),
          category: lint.lint_kind_pretty ? lint.lint_kind_pretty() : "Grammar",
          original: text.slice(span.start, span.end),
          start: span.start,
          end: span.end,
          replacements: replacements,
          json: lint.to_json()
        });
      }
      console.log(JSON.stringify(results));
    } catch (e) {
      console.error(JSON.stringify({ error: e.message }));
      process.exit(1);
    }
  });
});
