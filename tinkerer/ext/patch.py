'''
    patch
    ~~~~~

    Handles HTML link patching for images and cross-references. Sphinx
    generates these links as relative paths - aggregated pages and RSS
    feed require these to be patched.

    :copyright: Copyright 2011-2014 by Vlad Riscutia and contributors (see
    CONTRIBUTORS file)
    :license: FreeBSD, see LICENSE file
'''
from os import path
import re
import xml.dom.minidom

import pyquery

from tinkerer.ext.uistr import UIStr

try:
    from html.entities import name2codepoint
except:
    from htmlentitydefs import name2codepoint

try:
    import builtins as __builtin__
except:
    import __builtin__


# check whether unichr builtin exists, otherwise use chr
if "unichr" not in __builtin__.__dict__:
    unichr = chr



def build_html_only_codepoints():
    """
    Convert well formed HTML to XML by removing HTML only entity definitions.
    """
    html_name2codepoints = {}
    html_name2codepoints.update(name2codepoint)
    for name in ['amp', 'gt', 'lt', 'apos', 'quot']:
        if name in html_name2codepoints:
            del html_name2codepoints[name]
    return html_name2codepoints



HTML_ONLY_NAME2CODEPOINTS = build_html_only_codepoints()



def convert(s):
    """
    Take an input string s, find all things that look like SGML character
    entities, and replace them with the Unicode equivalent.

    Source:
    http://stackoverflow.com/questions/1197981/convert-html-entities-to-ascii-in-python/1582036#1582036
    """
    matches = re.findall("&#\d+;", s)
    if len(matches) > 0:
        hits = set(matches)
        for hit in hits:
            name = hit[2:-1]
            try:
                entnum = int(name)
                s = s.replace(hit, unichr(entnum))
            except ValueError:
                pass
    matches = re.findall("&\w+;", s)
    hits = set(matches)
    amp = "&"
    if amp in hits:
        hits.remove(amp)
    for hit in hits:
        name = hit[1:-1]
        if name in HTML_ONLY_NAME2CODEPOINTS:
            s = s.replace(hit,
                          unichr(HTML_ONLY_NAME2CODEPOINTS[name]))
    s = s.replace(amp, "&")
    return s



def patch_aggregated_metadata(context):
    """
    Patches context in aggregated pages
    """
    for metadata in context["posts"]:
        metadata.body = patch_links(
            metadata.body,
            metadata.link[:11], # first 11 characters is path (YYYY/MM/DD/)
            metadata.link[11:], # following characters represent filename
            True)      # hyperlink title to post
        metadata.body = strip_xml_declaration(metadata.body)



def patch_links(body, docpath, docname=None, link_title=False, replace_read_more_link=True):
    '''
    Parses the document body and calls patch_node from the document root
    to fix hyperlinks. Also hyperlinks document title. Returns resulting
    XML as string.
    '''
    doc = pyquery.PyQuery(body)
    patch_node(doc, docpath, docname)

    body = doc.html()
    if docname and replace_read_more_link:
        body = make_read_more_link(body, docpath, docname)

    if link_title:
        return hyperlink_title(body, docpath, docname)
    else:
        return body



def hyperlink_title(body, docpath, docname):
    """
    Hyperlink titles by embedding appropriate a tag inside
    h1 tags (which should only be post titles).
    """
    body = body.replace("<h1>", '<h1><a href="%s.html">' %
            (docpath + docname), 1)
    body = body.replace("</h1>", "</a></h1>", 1)
    return body



def make_read_more_link(body, docpath, docname):
    """
    Create "read more" link if marker exists.
    """
    doc = pyquery.PyQuery(body)
    link_p = ('<p class="readmorewrapper"><a class="readmore" '
              'href="%s.html#more">%s</a></p>' %
              (docpath + docname, UIStr.READ_MORE))
    doc('div#more').replaceWith(link_p)
    doc('p.readmorewrapper').next_all().remove()
    return doc.html()



def collapse_path(path_url):
    '''
    Normalize relative path and patch protocol prefix and Windows path separator
    '''
    return path.normpath(path_url).replace("\\", "/").replace(":/", "://")


def patch_node(node, docpath, docname=None):
    for img in node.find('img'):
        src = img.get('src', '')
        if src.startswith(".."):
            src = docpath + src
        src = collapse_path(src)
        img.set('src', src)

    for anchor in node.find('a'):
        ref = anchor.get('href')
        # skip anchor links <a name="anchor1"></a>, <a name="more"/>
        if ref != None:
            # patch links only - either starting with "../" or having
            # "internal" class
            is_relative = ref.startswith("../")
            if is_relative or "internal" in anchor.get('class'):
                ref = docpath + ref

            # html anchor with missing post.html
            # e.g. href="2012/08/23/#the-cross-compiler"
            # now href="2012/08/23/a_post.html#the-cross-compiler"
            ref = ref.replace("/#", "/%s.html#" % docname)

            # normalize urls so "2012/08/23/../../../_static/" becomes
            # "_static/" - we can use normpath for this, just make sure
            # to revert change on protocol prefix as normpath deduplicates
            # // (http:// becomes http:/)
            ref = collapse_path(ref)
            anchor.set('href', ref)


def strip_xml_declaration(body):
    """
    Remove XML declaration from document body.
    """
    return body.replace('<?xml version="1.0" ?>', '')

