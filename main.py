import pilates

if __name__ == "__main__":
    img = pilates.Image.from_file("test.png")
    img = pilates.Image.new_image(background_colour=[255,105,180])
    img.set_bit_depth(16)
    
    with open("out.png","wb") as f:
        f.write(img.to_bytes())


