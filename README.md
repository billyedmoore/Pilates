# PILates

Alternative python PNG library no one should ever use.

## Features

Read a PNG from a file into an Image object.
```python 
img = pilates.Image.from_file("filename.png")
```
Create a PNG from a scratch, with or without a given background colour.
```python 
# Create a new image with a pink background
img = pilates.Image.new_image(background_colour=[255,105,180])
```
+ Get a pixels from an Image.
```python 
# get all pixels from an image
pixels: List[List[List[int]]] = img.get_pixels() 

# get an individual pixel by coord here x=1 y=1
pixel: List[int] = img.get_pixel(1,1)
```
Change features of the image. 
(Note these couldn't all be applied to the same image)
```python
# convert a truecolour image to grayscale
img.to_grayscale()

# convert a grayscale image to truecolour
img.to_truecolour()

# add an alpha channel to an image without one
img.add_alpha()

# remove the alpha channel to an image with one 
img.remove_alpha()
```
Apply transforms to the image including:
+ **Resize**: using bi-linear sampling. 
+ **Sort**: sort pixels by darkness.
+ **Invert**: invert the colour.
```python 
# Resize img to 100x100
transform = pilates.Resize(100,100)
img.apply_transform(transform)
```
Write the image to a PNG file.
```python 
img.to_file("file.png")
```
## Limitations

+ No support for encoding or decoding interlaced images. 
+ Encoded images have filter method 0 for all lines (no filtering is applied). There is however full support for decoding images with alternate filter methods.
+ Only critical chunks are being encoded and decoded. Ancillary chunks are ignored.
