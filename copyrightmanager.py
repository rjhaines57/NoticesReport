from blackduck.HubRestApi import HubInstance
import regex
import html2text
import unicodedata, itertools, sys
import logging

class CopyrightManager:
    """Manage copyrights for a BOM component"""
    component_name = ""
    hubInstance = None
    origin = None
    copyrights = None

    def __init__(self, hub, component_name, origin):
        self.hub = hub
        self.component_name = component_name
        self.origin = origin
        logging.debug(f"Created copyright manager for {self.component_name}")
        logging.debug(self.origin)
        self.load_copyrights()

    def load_copyrights(self):
        url = self.hub.get_link(self.origin, "component-origin-copyrights")
        url = url + "?limit=9999"
        self.copyrights = self.hub.execute_get(url).json().get('items', [])
        logging.debug("length {}".format(len(self.copyrights)))

    def disable_all_copyrights(self, source='KB'):
        for copyright in self.copyrights:
            if source != copyright['source']:
                continue
            copyright.update({'active': False})

        url = self.hub.get_link(self.origin, "component-origin-copyrights")
        response = self.hub.execute_put(url, data=self.copyrights)


    def delete_all_custom_copyrights(self, source='CUSTOM'):
        for copyright in self.copyrights:
            if source != copyright['source']:
                continue
            url = copyright['_meta']['href']
            response = self.hub.execute_delete(url)
            logging.debug(f"{source} {url} {response}")

    # if args.not_filtered:
    #     copyright = copyright_entry['updatedCopyright'].replace("\r\n", " ").replace("\n", " ")
    #     copyright = copyright_entry['updatedCopyright']
    #     logging.debug("->" + copyright)
    #     output_file.write("   " + copyright + "\n")
    #
    #     return





    def remove_control_chars(self, s):
        all_chars = (chr(i) for i in range(sys.maxunicode))
        categories = {'Cc'}
        control_chars = ''.join(map(chr, itertools.chain(range(0x00, 0x20), range(0x7f, 0xa0))))

        control_char_regex = regex.compile('[%s]' % regex.escape(control_chars))

        return control_char_regex.sub(' ', s)

    def preprocess_copyrights(self):
        """ Process raw copyrights to remove unnecessary text"""
        processed_copyrights = []
        for copyright_entry in self.copyrights:

            logging.debug("raw copyright:" + copyright_entry['updatedCopyright'])
            if not copyright_entry['active']:
                continue

            logging.debug("raw copyright:"+copyright_entry['updatedCopyright'])
            # Remove copyright symbols and replace with "(C)"
            copyright_text = copyright_entry['updatedCopyright'].replace("&copy", "(C)").replace("&#169;", "(C)")


            # Convert any html to text
            copyright_text = html2text.html2text(copyright_text)

            # Remove any non unicode characters
            copyright_text = self.remove_control_chars(copyright_text)

            # Remove new lines
            copyright_text = copyright_text.replace("\r\n", " ").replace("\n", " ")  # Remove all newlines
            copyright_text = copyright_text.replace("\\n", " ") # Remove all "newlines"

            # Remove comments delimiters
            copyright_text = copyright_text.replace("-->", "").replace("<!--", "")  # XML
            copyright_text = copyright_text.replace("// ", "").replace(" //", "").replace("/*", "").replace("*/",
                                                                                                  "")  # Remove comments (C-like)
            copyright_text = copyright_text.replace("#", "")  # Remove comments (Shell)
            copyright_text = copyright_text.replace("rem ", "")  # Batch scripts?

            # Remove < > and [ ] , typically used around mail and urls e.g. <fred@flintstones.com>
            copyright_text = copyright_text.replace("<", "").replace(">", "")
            copyright_text = copyright_text.replace("[", " ").replace("]", " ")

            # Remove * and ~ , this often comes from comments where there is a box of asterisks like this:
            # **************
            # * box of text
            # **************
            copyright_text = copyright_text.replace("*"," ")
            copyright_text = copyright_text.replace("~ ~","")

            # Remove ============= , happens Often used to delineate text. i.e:
            # ===================================
            # copyright (C) 2020 Rob Haines
            copyright_text = regex.sub("======.*", "", copyright_text, flags=regex.IGNORECASE)

            # Clean up whitespace
            copyright_text = copyright_text.strip()
            copyright_text = regex.sub("\s+", " ", copyright_text)  # Reduce Multiple spaces to single spaces to improve merge


            # Remove "all rights reserved". Need to check if this is OK? Possibly add it back again after merging?
            copyright_text = regex.sub("All rights Reserved.*", "", copyright_text, flags=regex.IGNORECASE)


            # Licence Cleanup - Where copyright is part of a license, e.g.
            # copyright (C) 2020 Rob Haines. This library is free software ....
            copyright_text = regex.sub("This library is free software.*", "", copyright_text,
                                  flags=regex.IGNORECASE)
            copyright_text = regex.sub("under the terms of.*", "", copyright_text, flags=regex.IGNORECASE)
            copyright_text = regex.sub("Licensed under.*", "", copyright_text, flags=regex.IGNORECASE)
            copyright_text = regex.sub("Released under.*", "", copyright_text, flags=regex.IGNORECASE)
            copyright_text = regex.sub("Permission is hereby.*", "", copyright_text, flags=regex.IGNORECASE)
            copyright_text = regex.sub("This product includes software.*", "", copyright_text,
                                  flags=regex.IGNORECASE)  # Seems to be common in apache
            copyright_text = regex.sub("The .* licenses this file.*", "", copyright_text,
                                  flags=regex.IGNORECASE)  # Seems to be common in apache code
            copyright_text = regex.sub("Verbatim copying and distribution.*", "", copyright_text,
                                  flags=regex.IGNORECASE)
            copyright_text = regex.sub("This (file )*is free software.*", "", copyright_text,
                                  flags=regex.IGNORECASE)
            copyright_text = regex.sub("This program is made available under.*", "", copyright_text,
                                  flags=regex.IGNORECASE)

            # Code cleanup, where copyrights are added to code, often there are keywords that can be used
            # to show where the copyright ends and the code starts, happens often in minified java script
            copyright_text = regex.sub("package \w.*", "", copyright_text)  # Remove where is copyright is part of java file
            copyright_text = regex.sub("@(Deprecated|SuppressWarnings|version|param).*", "",
                                  copyright_text)  # part of java file
            # Javascript
            copyright_text = regex.sub("(static|public|protected|private|class|interface).*", "",copyright_text)


            # And finally....
            copyright_text = regex.sub('[,.]\s?$', '', copyright_text)  # Punctuation? Where were going we don't need punctuation.
            copyright_text = regex.sub('".*', '', copyright_text)
            copyright_text = copyright_text.strip()

            logging.debug("processed copyright:" + copyright_text)
            copyright_entry["processed_copyright"]=copyright_text


    def filter_copyrights(self):
        p = regex.compile(r'copyright[ ][^0-9]{0,20}[12][90][0-9]{2}|\(C\)[ ,\-:;\w]{5}|©[ ,\-:\w]{5}|@author', regex.IGNORECASE)
        matches = {}
        rejected_matches = []
        for copyright in self.copyrights:
            url = None
            if not copyright['active']:
                logging.debug("Skipping inactive copyright")
                continue

            copyright_text=copyright['processed_copyright']
            logging.debug("Trying to match: {}".format(copyright_text))
            # Look for url
            url_re = regex.compile(r"(\({0,1}+(?:https|http)://[^ ]*\){0,1})")
            url_matches = url_re.search(copyright_text)
            if url_matches:
                url = url_matches.group(1)
                copyright_text = copyright_text.replace(url, "")
                copyright_text = copyright_text.strip()
                copyright_text = regex.sub('[,.]\s?$', '', copyright_text)  # Punctuation? Where were going we don't need punctuation.
                logging.debug("Matched URL! :" + url)
                logging.debug("POST Processed:" + copyright_text + " url? "+str(url))
            key = copyright_text.lower()
            if p.search(copyright_text):

                if key not in matches:
                    matches[key] = {'url': {}, 'copyright': copyright_text, 'rejected': False}

                if url:
                    matches[key]['url'][url] = 1

                logging.debug("MATCHED Copyright text:" + copyright_text)
            else:
                rejected_matches.append(copyright['updatedCopyright'])

        return matches, rejected_matches


    def coalesce_dates(self, matches):
        newMatches = {}
        non_coerced = []
        coerced=[]
        coerce = []
        coerce.append(
            regex.compile(r'(?:\(c\)\s)((?:[12][90][0-9]{2}[\s,-]{1,3})+)(.*)$', regex.IGNORECASE))
        coerce.append(
            regex.compile(r'copyright\s(?:\(c\)\s|©\s){0,1}((?:[12][90][0-9]{2}[\s,]{1,3})+)(.*)$', regex.IGNORECASE))
        coerce.append(regex.compile(r'copyright\s(?:\(c\)\s|©\s){0,1}([12][90][0-9]{2}[-][12][90][0-9]{2}[\s,]{1,3})(.*)$',
                                    regex.IGNORECASE))
        for match in matches:

            found = False
            for reg in coerce:
                m = reg.search(matches[match]['copyright'])
                if m:
                    date = m.group(1)
                    holder = m.group(2)
                    logging.debug(f"    Coerced: {match}")
                    logging.debug( "     - Date:"+str(date)+" Holder:"+str(holder))
                    if not holder in newMatches:
                        newMatches[holder] = {'holder': holder, 'date': self.parse_date(date), 'url': matches[match]['url']}
                    else:
                        newMatches[holder]['date'].update(self.parse_date(date))
                    found = True
                    break

            if not found:
                non_coerced.append(matches[match]['copyright'])
        #				logging.debug(f"Not Coerced: {match}")


        for match in newMatches:
            # logging.debug(newMatches[match])
            output_string = "Copyright (C) {} {}".format(self.print_range(newMatches[match]['date']),
                                                                             newMatches[match]['holder'])


            # print_range(newMatches[match])
            if 'url' in newMatches[match]:
                urls = newMatches[match]['url'].keys()
                for url in urls:
                    output_string = output_string + " " + url
            coerced.append(output_string)

        return coerced,non_coerced

    def parse_date(self, date):
        date_range = regex.compile(r'([12][90][0-9]{2})[-]{1,}([12][90][0-9]{2})')
        date = date.replace(" ", "")
        date = regex.sub("-$", "", date)
        date_data = {}
        for adate in date.split(','):
            # logging.debug("ADATE:" + adate)
            adate = adate.strip()

            m = date_range.match(adate)

            if m:
                #	logging.debug("Matched ADATE:" + adate)
                start_date = m.group(1)
                end_date = m.group(2)
                for k in range(int(start_date), int(end_date) + 1):
                    date_data.update({k: 1})
            else:
                if adate != '':
                    try:
                        date_data.update({int(adate): 1})
                    except Exception as e:
                        logging.warning("Cannot parse date:"+adate+" Defaulted to 1970. ACTION REQUIRED - Please update this manually")
                        date_data.update({1970:1})



        return date_data


    def print_range(self, date):
        output = []
        year_list = list(date.keys())
        year_list.append(999999)
        year_list.sort()
        start_year = None
        last_year = None
        for year in year_list:
            # logging.debug("Process Year"+str(year))
            if start_year == None:
                start_year = int(year)
                last_year = int(year)
                continue

            if int(year) - last_year > 1:
                if start_year == last_year:
                    output.append(str(start_year))
                else:
                    output.append("{}-{}".format(str(start_year), str(last_year)))
                start_year = int(year)

            last_year = int(year)

        return ','.join(output)


    def get_copyrights(self, showRejected=False, annotateResults=False, unfiltered = False):

        if not unfiltered:
        #Preprocess copyrights to remove noise
            self.preprocess_copyrights()
            filtered_copyrights,rejected_copyrights=self.filter_copyrights()

            coalesced_copyrights,non_coalesced_copyrights = self.coalesce_dates(filtered_copyrights)

            output=coalesced_copyrights
            output.extend(non_coalesced_copyrights)
        #for output in coalesced_copyrights:
#            logging.debug(output)
#        for output in non_coalesced_copyrights:
#            logging.debug(output)
            return output,rejected_copyrights

        else:
            output=[]
            rejected_copyrights=[]
            for copyright_entry in self.copyrights:

                if not copyright_entry['active']:
                    continue

                logging.debug("raw copyright:" + copyright_entry['updatedCopyright'])
                output.append(copyright_entry['updatedCopyright'])
            return output,rejected_copyrights


