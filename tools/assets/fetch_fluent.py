"""Install the curated Microsoft Fluent Emoji illustrations (MIT) used as the channel's graphics preset.
Only the "Color" SVG style is used (crisp at any size); people use the "Default" skin-tone variant.

Get the source once (one archive download instead of hundreds of requests):
  mkdir -p SRC && curl -sSL https://codeload.github.com/microsoft/fluentui-emoji/tar.gz/refs/heads/main \
    | tar -xz -C SRC --wildcards "*/Color/*.svg" "*/metadata.json" "*/LICENSE"
Then:
  python tools/assets/fetch_fluent.py SRC [OUT=/srv/ytf/data/assets/fluent]
Writes OUT/<key>.svg, OUT/index.json ({key: {name, glyph, keywords, source}}) and OUT/LICENSE."""
import json, re, shutil, sys
from pathlib import Path


def key(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')


def main():
    src = next(Path(sys.argv[1]).glob('fluentui-emoji-*'))
    out = Path(sys.argv[2] if len(sys.argv) > 2 else '/srv/ytf/data/assets/fluent'); out.mkdir(parents=True, exist_ok=True)
    names = json.loads((Path(__file__).parent / 'fluent_catalog.json').read_text())
    index, missing = {}, []
    for n in names:
        d = src / 'assets' / n
        svgs = sorted(d.glob('Default/Color/*.svg')) or sorted(d.glob('Color/*.svg'))
        if not svgs:
            missing.append(n); continue
        k = key(n); shutil.copyfile(svgs[0], out / f'{k}.svg')
        meta = json.loads((d / 'metadata.json').read_text()) if (d / 'metadata.json').exists() else {}
        index[k] = {'name': n, 'glyph': meta.get('glyph', ''), 'keywords': meta.get('keywords', [])[:6],
                    'source': str(svgs[0].relative_to(src))}
    (out / 'index.json').write_text(json.dumps(index, indent=0, ensure_ascii=False))
    shutil.copyfile(src / 'LICENSE', out / 'LICENSE')
    print(f'{len(index)} graphics installed in {out}; missing: {missing}')


if __name__ == '__main__':
    main()
