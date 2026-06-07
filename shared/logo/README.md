# AlgoVoi Logo Assets

Official brand assets for AlgoVoi. Recreated from the AV mark used in the Operator Dashboard.

## Brand spec

- **Primary color**: `#0070f3` (brand-500)
- **Foreground**: pure white `#ffffff`
- **Wordmark color (light UI)**: `#111827` (gray-900)
- **Wordmark color (dark UI)**: `#f9fafb` (gray-50)
- **Typography**: Inter / system sans, weight 900 for "AV", weight 700 for "AlgoVoi"
- **Tile radius**: 25% of side length (e.g. 128px on a 512px tile)

## Files

| File | Dimensions | Use for |
|---|---|---|
| `algovoi-mark.svg` | 512×512 (scalable) | Source-of-truth vector, favicon, any size |
| `algovoi-mark-256.png` | 256×256 | Pabbly, small marketplace thumbnails, app icon |
| `algovoi-mark-512.png` | 512×512 | Shopify App Store, WordPress.org, Magento Marketplace |
| `algovoi-mark-1024.png` | 1024×1024 | Large-format hero, App Store icon source |
| `algovoi-wordmark.svg` | 1024×256 | Horizontal lockup on light backgrounds |
| `algovoi-wordmark-1024.png` | 1024×256 | Rasterized lockup for docs/README headers |
| `algovoi-wordmark-dark.svg` | 1024×256 | Horizontal lockup on dark backgrounds |
| `algovoi-wordmark-dark-1024.png` | 1024×256 | Rasterized dark-bg lockup |

## Regenerating PNGs

All PNGs are rendered from the SVG sources with [`@resvg/resvg-js-cli`](https://www.npmjs.com/package/@resvg/resvg-js-cli):

```bash
npx @resvg/resvg-js-cli --fit-width 512  algovoi-mark.svg     algovoi-mark-512.png
npx @resvg/resvg-js-cli --fit-width 256  algovoi-mark.svg     algovoi-mark-256.png
npx @resvg/resvg-js-cli --fit-width 1024 algovoi-mark.svg     algovoi-mark-1024.png
npx @resvg/resvg-js-cli --fit-width 1024 algovoi-wordmark.svg algovoi-wordmark-1024.png
npx @resvg/resvg-js-cli --fit-width 1024 algovoi-wordmark-dark.svg algovoi-wordmark-dark-1024.png
```

The SVG is the canonical source — regenerate PNGs whenever the SVG changes.

## Usage rights

Internal/product use only. For external brand use inquiries, contact the support address on https://algovoi.co.uk.
