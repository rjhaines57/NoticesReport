# Notices Report Generator

## Installation

Clone the repo from git hub and install the dependencies listed in the requirements file
```
python3 -m pip install -r requirements.txt
```

Create a new file called .restconfig.json in the directory where the script is cloned to. Here are templates depending on whether you are using a username password or API token:
```
{  
 "baseurl": "https://hub-hostname",
 "username": "<username goes here>",
 "password": "<password goes here>",
 "insecure": true,
 "debug": false
 }
```
Or
```
{  
 "baseurl": "https://hub-hostname",
 "api_token": "<API token goes here>",
 "insecure": true,
 "debug": false
}
 ```
Replace the URL with the url of your BlackDuck instance and add your credentials.

## Usage

usage: Generate notice report with filtered copyright information

       generate_notices_report.py 
       [-h] [-d] [-nf] [-nd] [-sr] [-o OUTPUT_TEXT]
       [-oh OUTPUT_HTML]   project_name version

positional arguments:
-  project_name - The name of the project in Blackduck
-  version - The name of the version in Blackduck

optional arguments:
-  -h, --help -            show this help message and exit
-  -d, --debug -           Enable debug output
-  -nf, --not_filtered - Don't perform any filtering
-  -sr, --show_rejected - Show all lines that were processed for copyright but were  ultimately rejected
-  -o \<filename\>, --output-text \<filename\>  - Output report as text
-  -oh \<filename\>, --output-html \<filename\> -  Output report as html


