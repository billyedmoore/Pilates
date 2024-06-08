import pilates

if __name__ == "__main__":
    img = pilates.Image.from_file("test.png")
    with open("out.png","wb") as f:
        f.write(img.to_bytes())


