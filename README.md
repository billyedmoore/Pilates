# PILates

Alternative python PNG library no one should ever use.

## Features

+ Decode a PNG from a file into an Image object.
+ Encode an image object into a (approximately) equivalent PNG. 

## Aspirational Features

+ Handle the compression and decompression without a library.
+ Have a series of transform classes that can be applied to an Image.
+ Ability to change the PNGs features:
    + Conversion between bit depths.
+ Support for encoding images with indexed colour (currently we convert to a
"normal" colour type under the hood)
+ Support for images with interlacing.
