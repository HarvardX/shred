# -*- coding: utf-8 -*-

import click
import csv
import html2text
import json
import logging
import os
import pathlib
import re
import shutil
import sys


@click.group()
def cli():
    pass


@cli.command()
@click.argument("inputfile", type=click.File("rb"))
@click.argument(
    "outpath",
    type=click.Path(
        exists=True,
        dir_okay=True, file_okay=False,
        writable=True, readable=True, path_type=pathlib.Path,
    )
)
@click.argument("prefix")
def process(inputfile, outpath, prefix):
    # get input text to be shredded
    contents = inputfile.read()
    json_contents = json.loads(contents)

    for e in json_contents:
        if e["type"] == "HLXP_HTML":
            filepath = outpath / "{}-{}.txt".format(prefix, e["uid"])

            h = html2text.HTML2Text()
            #h.skip_internal_links = True
            #h.ignore_anchors = True
            #h.ignore_images = True
            #h.ignore_emphasis = True
            #h.ignore_tables = True
            content = h.handle(e["data"]["content"])

            with filepath.open("w") as fd:
                fd.write(content)


def get_json_contents(filepath, as_list=False):
    """read filepath and return its results as list."""
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        print("json file({}) not found or not a file".format(filepath))
        return None

    # load json contents
    with open(filepath, mode="r", encoding="ISO-8859-1") as handle:
        contents = json.load(handle)

    if as_list:
        if isinstance(contents, dict):
            return contents.values()
        if isinstance(contents, list):
            return contents
        return None
    else:
        return contents


def get_csv_contents(filepath):
    """read filepath and return its results as list."""
    if not os.path.exists(filepath) or not os.path.isfile(filepath):
        print("csv file({}) not found or not a file".format(filepath))
        return None

    incsv = []
    with open(filepath, mode="r", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, dialect="excel")
        for row in reader:
            incsv.append(row)

    return incsv


def clean(name, maxi=70):
    result = re.sub("[^0-9a-zA-Z]+", "_", name)
    return result[0:maxi]  # capping name to maxi chars


def makefn(row):
    mod = "MODULE"
    if row["module"].startswith("Module"):
        mod = row["module"].split(":")[0]
    elif row["module"].startswith("Glossary"):
        mod = row["module"]
    modname = clean(mod)
    pagname = clean(row["page"])

    #if row["section"].startswith("Nameless"):
    #    _, sec = row["section"].split("Nameless ")
    #else:
    #    sec = row["section"]
    #secname = clean(sec)

    #return "{}-{}-{}".format(modname, pagname, secname)
    return "{}-{}".format(modname, pagname)


def collect_txt(outline):
    results = {}
    total_txt = 0
    total_video = 0

    for row in outline:
        if ("HTML" not in row["te_type"]) and ("VIDEO" not in row["te_type"]):
            continue

        fn = makefn(row)
        if fn not in results:
            results[fn] = {"txt": [], "video":[]}
        if "HTML" in row["te_type"]:  # element uid
            results[fn]["txt"].append(row["te_content_sample"])
            total_txt += 1
        if "VIDEO" in row["te_type"]: # transcript filename
            if len(row["filename"]) > 0:  # bogus video or transcript missing?
                results[fn]["video"].append({
                    "source": row["filename"],
                    "target": row["te_content_sample"].split("Video: ")[1],
                })
                total_video += 1
    return total_txt, total_video, results


@cli.command()
@click.option(
    "--csvfile",
    required=True,
    help="course sheet from colins lxp-web-utils",
)
@click.option(
    "--lxpdir",
    required=True,
    help="lxp bundle dir, where elements.json and repository are",
)
@click.option(
    "--outdir",
    required=True,
    help="where all text files are dumped",
)
def concat(csvfile, lxpdir, outdir):
    outline = get_csv_contents(csvfile)
    total_txt, total_video, txt_collection = collect_txt(outline)

    outline_json = os.path.join(outdir, "outline.json")
    with open(outline_json, "w") as ofh:
        ofh.write(json.dumps(txt_collection, indent=4))

    # lxp elements keyed by uid
    elements_content = get_json_contents(os.path.join(lxpdir, "elements.json"))
    elements = {x["uid"]:x for x in elements_content}

    # config html2text
    h = html2text.HTML2Text()
    h.image_to_alt = True
    for key, row in txt_collection.items():
        outfilepath = os.path.join(outdir, "{}.txt".format(key))
        if len(row["txt"]) > 0:
            content = ""  # have to accumulate txt because you never know
            for uid in row["txt"]:
                content += h.handle(elements[uid]["data"].get("content", ""))
            if len(content) > 0:
                print("---- writing to {}".format(outfilepath))
                with open(outfilepath, "w") as ofh:
                    ofh.write(content)
        if len(row["video"]) > 0:
            # copy transcript to output dir
            for v in row["video"]:
                source_fn = os.path.join(lxpdir, v["source"])
                if os.path.isfile(source_fn):
                    tgt = clean(v["target"].split(".mp4")[0])
                    target_fn = os.path.join(outdir, "{}.txt".format(tgt))
                    print("**** copying {} to {}".format(source_fn, target_fn))
                    shutil.copy(source_fn, target_fn)
                else:
                    print("xxxx transcript not found: {}".format(source_fn))

    print("---- done")

@cli.command()
@click.option(
    "--elements",
    required=True,
    help="elements.json filepath",
)
def check_elements(elements):
    outline = get_json_contents(elements)
    for r in outline:
        if "VIDEO" in r["type"]:
            if "transcript" in r["data"]:
                print("--- transcript.DATA: {}".format(r["data"]["transcript"]["key"]))
            elif "transcript" in r["meta"]:
                print("*** transcript.META: {}".format(r["meta"]["transcript"]["key"]))
            else:
                print("NNNNNNNNNNNNNNNN not found")


if __name__ == "__main__":
    sys.exit(cli())  # pragma: no cover
