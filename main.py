import pilates

if __name__ == "__main__":
    img: pilates.Image = pilates.Image.from_file("test.png")
    # img = pilates.Image.new_image(background_colour=[255,105,180])

    with open("out.png", "wb") as f:
        f.write(img.to_bytes())
