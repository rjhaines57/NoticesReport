#!/usr/bin/env python

import argparse
import json
import logging
import sys
import regex
from blackduck.HubRestApi import HubInstance
import html2text
import hashlib
from copyrightmanager import CopyrightManager


logging.basicConfig(format='%(asctime)s:%(levelname)s:%(message)s', stream=sys.stderr, level=logging.DEBUG)
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger().setLevel(logging.INFO)


parser = argparse.ArgumentParser("Retreive BOM component origin information, and additional information, for the given project and version")
parser.add_argument("project_name")
parser.add_argument("version")
parser.add_argument("-d","--debug", action="store_true",help="Enable debug")
parser.add_argument("-f","--file")
parser.add_argument("-nf","--not_filtered", action="store_true")
parser.add_argument("-nd","--no_date",action="store_true",)
parser.add_argument("-sr","--show_rejected", action="store_true", help="Show all lines that were processed for copyright but ultimately rejected")
parser.add_argument("-o","--output-text",help="Output report as text")
parser.add_argument("-oh","--output-html",help="Output report as html")
parser.add_argument("--save_json",help="Store the query made to the database, use option --use_json to re-use data. This option is for re-running the script offline to improve results")
parser.add_argument("--use_json",help="Store the query made to the database, use option --use_json to re-use data. This option is for re-running the script offline to improve results")

#parser.add_argument("-c", "--copyright_info", action="store_true", help="Include copyright info from the Black Duck KB for (KB) components in the BOM")

args = parser.parse_args()

if args.debug:
	logging.getLogger("requests").setLevel(logging.DEBUG)
	logging.getLogger("urllib3").setLevel(logging.DEBUG)
	logging.getLogger().setLevel(logging.DEBUG)



if not args.output_text and not args.output_html:
	print("You must select either html (-oh)  or text (-o) output ")
	parser.print_help()
	sys.exit(1)

logging.info("Requesting bom from hub")
hub = HubInstance()
project = hub.get_project_by_name(args.project_name)
version = hub.get_version_by_name(project, args.version)

bom_components = hub.get_version_components(version).get('items', [])
logging.debug("bom_components: {}".format(bom_components))

if not args.use_json:
	new_components=[]
	for bom_component in bom_components:
		logging.debug("Checking component {} for sub components".format(bom_component['componentName']))
		if bom_component['matchTypes'][0] == "MANUAL_BOM_COMPONENT": # and bom_component['componentName'] in proj_list:
			sub_project = hub.get_project_by_name(bom_component['componentName'])
			if sub_project != "" and sub_project != None:
				sub_version = hub.get_version_by_name(sub_project, bom_component['componentVersionName'])
				if sub_version != "" and sub_version != None:
					logging.debug("Processing project within project '{}'".format(bom_component['componentName']))
					sub_bom_components = hub.get_version_components(sub_version).get('items', [])

					new_components.extend(sub_bom_components)
					logging.debug("Number of components:"+str(len(new_components)))
	bom_components.extend(new_components)

if args.save_json:
	with open(args.save_json, "w",encoding="utf-8") as f:
		json.dump(bom_components, f)



all_origins = dict()
all_origin_info = {}
scan_cache = {}
licenses = {}
license_by_component={}
copyrights = {}


def process_bom(hub,bom_components):

	logging.info("Processing {} bom entries: ".format(len(bom_components)))
	count=len(bom_components)

	duplicate_check={}
	for bom_component in bom_components:


		if 'componentVersionName' in bom_component:
			bom_component_name = f"{bom_component['componentName']}:{bom_component['componentVersionName']}"
		else:
			bom_component_name = f"{bom_component['componentName']}"

		count=count-1
		logging.info("Processing: {} {} remaining".format(bom_component_name,count))

		if bom_component_name in duplicate_check:
			logging.warning("Skipping {} : Already processed".format(bom_component_name))
		else:
			duplicate_check[bom_component_name]=True

		# Component details include the home page url and additional home pages
		component_url = bom_component['component']
		component_licenses = hub.get_license_info_for_bom_component(bom_component)


		logging.debug("component_licenses: {}".format(component_licenses))
		for license in component_licenses.keys():
			if not license in licenses:
				licenses[license]={'components' : [bom_component_name], 'text' : component_licenses[license]['license_text_info']}
				license_by_component[bom_component_name]=license
			else:
				licenses[license]['components'].append(bom_component_name)


		#
		# Grab origin info, file-level license info, and file-level copyright info
		#
		all_origin_details = list()
		for origin in bom_component.get('origins', []):
			logging.debug(f"Retrieving origin details for {bom_component_name} and origin {origin['name']}")
			origin_url = hub.get_link(origin, 'origin')
			origin_details = hub.execute_get(origin_url).json()
			#logging.debug("Origin: {}".format(origin))
			#
			# Add deep license info and copyright info, as appropriate
			#
			info_to_get = []
			info_to_get.extend([
						("component-origin-copyrights", "component_origin_copyrights")
					])
			for link_t in info_to_get:
				link_name = link_t[0]
				k = link_t[1]
				url = hub.get_link(origin_details, link_name)
				copyrightmanager=CopyrightManager(hub,bom_component_name, origin)
				copyright_list, rejected_copyrights=copyrightmanager.get_copyrights()
				if 'externalId' in origin:
					key=origin['externalId']
				else:
					key = origin['name']

				if key not in copyrights:
					copyrights.update({bom_component_name : { key: { 'copyrights' : copyright_list, 'rejected' : rejected_copyrights } }})
				else:
					copyrights[bom_component_name][key]['copyrights'].extend(copyright_list)
					copyrights[bom_component_name][key]['rejected'].extend(rejected_copyrights)
			#	copyrightmanager.disable_all_copyrights()
			#	copyrightmanager.delete_all_custom_copyrights()




def generate_text_report():

	output_string="\n"+args.project_name+" "+args.version+"\n========\n\n"
	for component in copyrights.keys():
		output_string=output_string+"\n"
		for origin in copyrights[component]:
			output_string=output_string+"{} {}\n".format(component,origin)
			if component in license_by_component:
				output_string=output_string+"License: {}\n\n".format(license_by_component[component])

			output_string = output_string + "Copyrights:\n"
			for copyright in copyrights[component][origin]['copyrights']:
				output_string=output_string+"  "+ copyright+"\n"
			if args.show_rejected:
				for copyright in copyrights[component][origin]['rejected']:
					output_string = output_string + "  REJECTED: "+copyright + "\n"


	output_string=output_string+"\n\nLicenses\n=======\n\n"
	for license in licenses:
		output_string=output_string+license+"\n"
		output_string=output_string+"({})\n".format(','.join(licenses[license]['components']))
		output_string=output_string+"\n\n"+ licenses[license]['text']
		output_string=output_string+"\n\n"

	return output_string

def generate_html_report():

	output="""
<!doctype html>

<html lang="en">
<head>
  <meta charset="utf-8">

  <title>Notices Report</title>
  <meta name="description" content="Notice Report">
  <meta name="author" content="BlackDuck">
</head>

<body>
<h1>{} {}<h1>
""".format(args.project_name,args.version)


	for component in copyrights.keys():
		for origin in copyrights[component]:
			if not copyrights[component][origin]:
				continue
			output=output+"<h2>{} {}</h2>".format(component,origin)
			if component in license_by_component:
				output = output + "<h4>License: {}</h4>".format(license_by_component[component])
			output = output + "<h4>Copyrights:</h4><ul>"
			for copyright in copyrights[component][origin]['copyrights']:
				output=output+"<li>{}</li>".format(copyright)
			if args.show_rejected:
				for copyright in copyrights[component][origin]['rejected']:
					output = output + "<li style=\"color:red;\">REJECTED: {}</li>".format(html2text.html2text(copyright))

			output = output + "</ul>"

	output=output+"<h1>Licenses</h1>"
	for license in licenses:
		output=output+"<h2>{}</h2>".format(license)
		output=output+"<h3>({})</h3>".format(','.join(licenses[license]['components']))
		output=output+"<pre>{}<pre>".format(licenses[license]['text'])


	output = output + """
	  <script src="js/scripts.js"></script>
	</body>
	</html>	
	"""

	return output

if args.use_json:
	with open(args.use_json) as f:
		all_origin_info = json.load(f)
else:
	process_bom(hub, bom_components)
	if args.output_html:
		with open(args.output_html,"w", encoding="UTF-8") as html:
			logging.info("Writing html output to:{}".format(args.output_html))
			html.write(generate_html_report())

	if args.output_text:
		with open(args.output_text,"w", encoding="UTF-8") as text:
			logging.info("Writing text output to:{}".format(args.output_text))
			text.write(generate_text_report())




