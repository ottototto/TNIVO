# TNIVO File Organizer

TNIVO is a powerful and easy-to-use file organizer. It helps you manage your files efficiently and easily with a user-friendly interface.

## Features

- Organize your files based on file type
- Easy to use drag and drop interface
- Search functionality to easily locate your files
- Supports various file types: documents, images, audio, video, etc.

## Installation

Clone the repository:

```bash
git clone https://github.com/yourusername/TNIVO.git
```

Navigate to the TNIVO directory:

```bash
cd TNIVO
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
python src/main.py
```

## Usage

## Organize using Regular Expressions with TNIVO

TNIVO allows you to use regular expressions (regex) to filter and organize your files. Regular expressions are a powerful tool for matching patterns in text, which makes them ideal for tasks like this.

Here's a basic guide on how to use them in our application:

1. **Access the regex input field**: This is where you'll enter your regular expression. The application will use this to match video file names.

2. **Write your regular expression**: If, for example, you want to match all files that start with 'vacation' and end with '.mp4', your regex would be `^vacation.*\.mp4$`.

   - `^` denotes the start of the line.
   - `vacation` is the exact text we want to match at the start of the file name.
   - `.*` matches any character (.) any number of times (\*).
   - `\.` matches the dot before the file extension. The backslash is necessary because a dot has a special meaning in regex, and the backslash 'escapes' this special meaning.
   - `mp4` is the exact text we want to match at the end of the file name.
   - `$` denotes the end of the line.

3. **Apply the filter**: After entering your regex, you can click Organize and the application will then organize your files based on the matches.

Remember, regular expressions are very powerful, but they can also be quite complex. Make sure to test your regular expression before applying it to your video files.


## Revert changes

If you wish to revert changes made by TNIVO, you can click the "Reverse" selection active and click "Organize". This will revert previous actions made by TNIVO. 
**IMPORTANT** -- Revert uses the tnivo.log file to see what changes were made so **do not** delete it unless you're completely certain everything is alright. 

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

## License

<p xmlns:cc="http://creativecommons.org/ns#" xmlns:dct="http://purl.org/dc/terms/"><a property="dct:title" rel="cc:attributionURL" href="https://github.com/ottototto/TNIVO">TNIVO</a> by <a rel="cc:attributionURL dct:creator" property="cc:attributionName" href="https://github.com/ottototto">github.com/ottototto</a> is licensed under <a href="http://creativecommons.org/licenses/by-nc-sa/4.0/?ref=chooser-v1" target="_blank" rel="license noopener noreferrer" style="display:inline-block;">CC BY-NC-SA 4.0<img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/cc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/by.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/nc.svg?ref=chooser-v1"><img style="height:22px!important;margin-left:3px;vertical-align:text-bottom;" src="https://mirrors.creativecommons.org/presskit/icons/sa.svg?ref=chooser-v1"></a></p>

```