# RecallCheck product identity

RecallCheck uses one product mark across favicon, installed app, and share surfaces.

## Canonical mark
- **Concept:** barcode recognition + one pink recall signal bar.
- **Navy:** `#07111F`
- **White:** `#F4F7FF`
- **Signal pink:** `#FF66C4`
- **Rule:** never add initials, gradients, glow, slogans, badges, or extra decoration to the mark.
- **Small-size behavior:** preserve the six-bar silhouette and pink final bar. The mark must remain legible at favicon size.

## Product mark
`assets/icons/recallcheck.svg` is the single canonical mark. It is the favicon and the source identity for installed and shared experiences.

## App / Home Screen icon
The web app manifest references the canonical SVG directly with `purpose: any maskable`. The mark contains its own navy field and generous safe area so operating systems can apply platform masks without clipping the barcode.

## Social / share image
`assets/social/recallcheck-share.svg` is a 1200×630 composition containing only the canonical mark on the navy field. The mark is centered inside a conservative safe area so square, landscape, and aggressively cropped previews retain the identity.

## Product principle
Metadata supplies the product name and description. The image supplies recognition. Do not turn the share image into an advertisement.
