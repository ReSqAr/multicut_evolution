#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
    multicut_evolution -- Eine erweiterte Pythonversion von multicut_light.
    Copyright (C) 2010-2012  Yasin Zähringer (yasinzaehringer+dev@yhjz.de)
              (C) 2011-2012  Matthias Kümmerer
              (C) 2011-2012  Felix Lenders

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program. If not, see <http://www.gnu.org/licenses/>.
"""

import subprocess
import os, shutil, codecs, pwd
import httplib, mimetypes
import time
import random
import tempfile
import traceback
import urllib
import urllib2
import re
import sys
import datetime
import optparse
import hashlib
import ast
import fcntl

import base64
from fractions import Fraction

C_CLEAR			= "\033[0m"
C_RED			= "\033[41;37;1m"
C_BLUE			= "\033[44;37;1m"
C_BLACK			= "\033[40;37;1m"
C_RED_UNDERLINE	= "\033[41;37;1;4m"
C_BOLD			= "\033[1m"
C_BOLD_UNDERLINE= "\033[1;4m"

multicut_evolution_date = "15.11.2012"
prog_id = "multicut_evolution/%s" % multicut_evolution_date
VERBOSITY_LEVEL = 0

#
# Help texts
#
prog_help = \
"""
Hilfe für multicut_evolution.py ({VERSION}):

multicut_evolution.py [--help] [--verbosity $d] [<andere Optionen>] $datei1 ...

Die übergebenden Dateien werden anhand von auswählbaren Cutlists geschnitten.
Dies geschieht in mehreren Phasen, die weiter unten beschrieben werden.

{BOLD}Optionen{CLEAR}
    -h, --help
        Zeigt dise Hilfe an

    --inst-help
        Zeigt an, welche Programme in welchen Versionen benötigt werden und
        wie diese konfiguriert werden müssen.

    --config-help
        Gibt eine Übersicht zu den verschiedenen Optionen in der Konfigurationsdatei.

    -n, --nocheck
        Geschnittene Dateien werden nicht zur Überprüfung
        wiedergegeben.

    -i, --only-internet
        Falls online keine Cutlist gefunden werden kann, wird nicht
        danach gefragt, ob der Benutzer eine eigene anlegen will.

    -o, --no-internet, --offline
        Es wird nicht online nach Cutlists gesucht und es werden keine
        Kommentare von OnlineTVRecorder geladen.

    -c, --no-comments
        Es werden keine Kommentare von OnlineTVRecorder geladen.

    -s, --no-suggestions
        Dateinamenvorschläge von Cutlists werden nicht berücksichtigt.

    --config $name
        Gibt den Namen der zu verwendenden Konfigurationsdatei an.
        [default: ~/.multicut_evolution.conf]

    --verbosity $d
        Debuginformationen werden entsprechend ausgegeben.
        [default: 0, maximal 5]

{BOLD}Ablauf eines Schneidevorgangs{CLEAR}
    Phase 1 - Auswahl oder anlegen einer Cutlist
        Für jede angegebene Datei wird eine Cutlistübersichtsseite angegeben. Daraus
        kann man eine Cutlist auswählen, in dem man die Nummer eintippt und mit
        Enter bestätigt und testen, indem man 'test $d' (wobei $d die Nummer der
        Cutlist ist) eintippt und mit Enter bestätigt. Einfach ohne Eingabe Enter
        drücken, bewirkt, dass keine Cutlist ausgewählt wird (und damit die Datei
        nicht geschnitten).
        Wenn allerdings keine Cutlist gefunden wurde, weil z.B. noch niemand eine
        Cutlist hochgeladen hat, dann besteht die Möglichkeit eine eigene Cutlist
        anzulegen. Wenn man mit den existierenden Cutlists unzufrieden ist, kann
        man auch in diesen Modus wechseln, indem man 'own' bei der Auswahl eingibt.
        Mit 'n' kann man nun eine neue Cutlist anlegen, dazu wird Avidemux
        gestartet. Man kann nun dort framegenau Segmente des Films herausnehmen
        und mit Speichern diese Informationen multicut verfügbar machen.
        Nachdem für alle Filme eine Cutlist ausgewählt wurde, hat man die Option
        einzelne Cutlists umzuwählen oder alle zu bestätigen. Bestätigen
        funktioniert einfach durch Enter drücken. Das Umwählen von Cutlists wird
        durch Eingeben der zu den Filmen gehörenden Nummern ausgelöst. Dabei sind
        Eingaben wie '1,2-5' zulässig.

    Phase 2 - Schneiden
        In dieser Phase ist keine Benutzerinteraktion notwendig.

    Phase 3 - Überprüfen der Schnitte
        Nun können die Filme ausgewählt werden, die überprüft werden sollen. Dabei
        können gewisse Filme angegeben durch ihre Nummer oder man überprüft alle
        noch nicht überprüften Filme durch Eingabe von 'a'. Alternativ kann man alle
        Filme überprüfen (auch die, die schon überprüft wurden) durch Eingabe von
        'f'. Desweiteren kann man das Programm durch 'n' beenden.

        Das Überprüfen untergliedert sich weiter, zu erst werden die Schnitte
        angezeigt, danach kann man die Cutlist bewerten mit Noten zwischen 0 - 5.
        (0 = schlechteste, 5 = beste Bewertung) Seien Sie fair! Danach kann man
        angegeben, ob die geschnitte Datei gelöscht werden soll, was z.B. nach
        Fehlschnitten hilfreich ist. Dabei wird die Originaldatei an ihren
        ursprünglichen Ort zurückverschoben.
        Bei eigenen Cutlists werden nachdem Überprüfen der einzelnen Schnitten
        einige Angaben vor dem Hochladen abgefragt. Allerdings ist Hochladen nur
        möglich, wenn der Cutlist.at-Benutzerhash angegeben wurde.
""".format(VERSION=multicut_evolution_date,BOLD=C_BOLD,CLEAR=C_CLEAR)

prog_config_help = \
"""
{BOLD_UNDERLINE}Konfigurationsdatei{CLEAR}
    In der Konfigurationsdatei zur Verfügung stehenden Einstellungen (der
    Standardpfad für die Konfigurationsdatei ist '~/.multicut_evolution.conf'):
        avidemux_gui=
            Befehl zum Ausführen einer Avidemux-Version mit GUI. (Kein Pfad)
            [default: avidemux2_qt4]
        virtualdub=
            Pfad zu vdub.exe [default: None]
            Am besten einfach otr-verwaltung von monarc klonen
            (https://github.com/monarc99/otr-verwaltung), und das
            vdub.exe aus dem dortigen monarc-Branch verwenden. Dann sind
            alle Bibliotheken korrekt installiert.

        cutdir=
            Ausdruck für Ausgabepfad [default: .]
        cutname=
            Ausdruck für Ausgabename (s.u.) [default: {{base}}-cut{{rating}}.{{ext}}]
        uncutdir=
            Ausgabepfad für alte Dateien [default: .]
        uncutname=
            Ausdruck für Ausgabename (s.u.) [default: {{full}}]
        suggestions=
            Dateinamenvorschläge von Cutlists werden berücksichtigt. [default: true]
	nfo=
	    Sucht auf IMDB nach Filmnamen und speichert IMDB-Link in .nfo ab, damit
	    es z.B. der XBMC-Scraper nutzen kann. [default: false]

        author=
            Gibt den Namen an, der als Autor für selbsterstelte Cutlists verwendet
            wird. [default: Terminalbenutzername]
        cutlistathash=
            Cutlist.at-Benutzerhash, also nicht die gesamte URL sondern nur den Hash
            [default: leer]

        comments=
            Kommentare von OnlineTVRecorder werden angezeigt. [default: true]
        review=
            Gibt an, ob nach einer Wertung gefragt werden soll. [default: true]
        vorlauf=
            Vorlauf bei der Überprüfung [default: 10]
        nachlauf=
            Nachlauf bei der Überprüfung [default: 5]

        ac3fix=
            Pfad von ac3fix.exe (inklusive ac3fix.exe). Default: None
        useac3=
            Bestimmt, ob AC3 sofern vorhanden in die HD-AVI gemuxt werden soll.
            Im Moment sehr experimentell! [default: false]
        convertmkv=
            Bestimmt, ob die geschnittene AVI-Datei danach noch in MKV kopiert
            werden soll. [default: false]
        convertonlywac3tomkv=
            Konvertiert nur Videos nach MKV, für die eine AC3-Datei vorliegt.
            [default: false]
        delavi=
            Bestimmt, ob die AVI-Datei nach der Konvertierung in MKV gelöscht
            werden soll. [default: false]
        cachedir=
            Pfad zu Cache [default: ~/.cache/mutlicut/]
            Ein leerer Pfad bedeutet kein Caching von herunterladen Cutlists.

            
    Beschreibung der Sprache für die Namensgebung von Dateien:
    (siehe auch cutname=, uncutname=)
        {{base}}       Dateiname ohne Endung
        {{ext}}        Dateiendung
        {{shortext}}   Dateiendung ohne mpg.
        {{rating}}     Bewertung der Cutlist *100
        {{full}}       Der gesamte Dateiname
""".format(BOLD_UNDERLINE=C_BOLD_UNDERLINE,BOLD=C_BOLD,CLEAR=C_CLEAR)

prog_inst_help = \
"""
{BOLD_UNDERLINE}Benötigte Programme und deren Konfiguration{CLEAR}

{BOLD}Programme{CLEAR}
    {BOLD}Avidemux{CLEAR}
        Beliebige Version
        Ubuntu/Debian Paket: avidemux-cli avidemux-qt
    {BOLD}Wine{CLEAR}
        Beliebige Version
        Ubuntu/Debian Paket: wine oder wine1.3
    {BOLD}VirtualDub{CLEAR} (Windowsprogramm via Wine)
        Version: 1.7.8.28346
        Link: http://sourceforge.net/projects/virtualdub/files/virtualdub-win/1.7.8.28346/
    {BOLD}ffdshow{CLEAR} (Windowsprogramm via Wine)
        Version: 2946
        Link: http://sourceforge.net/projects/ffdshow-tryout/files/SVN%20builds%20by%20clsid/ffdshow_rev2946_20090515_clsid.exe

    {BOLD}mkvmerge{CLEAR} [optional]
        Beliebige Version
        Ubuntu/Debian Paket: mkvtoolnix; für eigene Experimente ist mkvtoolnix-gui noch ganz angenehm
    {BOLD}ac3fix{CLEAR} (Windowsprogramm via Wine) [optional]
        Zum Reparieren beschädigter AC3-Dateien. Da die Reparatur nicht gut genug ist,
        wird es hier nur verwendet, um die AC3-Dateien auf Korrektheit zu überprüfen.
        Link: http://www.videohelp.com/tools/AC3Fix

{BOLD}Konfiguration{CLEAR}
    {BOLD}Avidemux{CLEAR}
        [TODO]
    {BOLD}VirtualDub{CLEAR}
        [TODO]
    {BOLD}ffdshow{CLEAR}
        Wie hier beschrieben: http://www.otrforum.com/showthread.php?t=53996&p=308679&viewfull=1#post308679
        Starte Konfigurationsdialog mittels
            wine rundll32.exe ~/.wine/drive_c/windows/system32/ff_vfw.dll,configureVFW
        Danach Einstellungen setzen wie in obigem Forenbeitrag dargestellt.
""".format(BOLD=C_BOLD,BOLD_UNDERLINE=C_BOLD_UNDERLINE,CLEAR=C_CLEAR)

print "multicut_evolution.py Copyright (C) 2010-2012  Yasin Zähringer (yasinzaehringer+dev@yhjz.de)"
print "                                (C) 2011-2012  Matthias Kümmerer"
print "                                (C) 2011-2012  Felix Lenders"
print "(URL: http://www.yhjz.de/www/linux/prog/multicut_evolution.html)"
print "This program comes with ABSOLUTELY NO WARRANTY."
print

executiondir = os.path.split(os.path.abspath(sys.argv[0]))[0]
def get_comp_data_dx50():
    """ Encoder: MPEG4, FourCC: DX50 """

    return '2935,"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"'
 
 
def get_comp_data_h264_43():
    """ Encoder: H.264; FourCC: H.264, CQ 22, Darstellungsverhältnis 4:3
von monarc99 """
    
    return '2992,"ADLICwAAAADRC1lWMTK6C5CyCAAnDf////8ZDRAQEBDiDBUWFxjLDBcZGxzUDBkaHB5BDAAAAAAqDAEAAAAzDDIAAADlC20BzpUA15QABS0NCgAAAB8NfQLonQXxlAAE2gwREhMUlY0BR5QABlAMHgAAADkMZFYJ6wtnC/QLBE0K3YwBBAUNAgAAAO6EBQT3DBEBAABkjwFNDDxdAlaNED+FAvqdBcOWAAsNfQgUnRf9lQNqlQBcnwUlDB9ZA+CFBcmXANILBlQPBLsLFgAAABqUBgAB4wwaGxwezAwUFRYX1QwgIyYpeY8HQgwURAUEKwx9AAAANI0f5p0dz50I2JQABQANuAsAAOkMfSnynQ7bjSiWjxxRDBlVDDqNAeyfBfULCE0ZBo8W7wwAUQH4hx1lDEZdAk6HCFcM9EopIAx1IfuFDsSNBwydIxWNFv6EBQTQDBYXGBprjQFdhRQmlQbKlQbTlwa8C1VVGBuVBuScBQrNDBgaHB7WDBscHiCRjQdDhR0shR01nQjnjQfwlQDZlUUBnTvzngXcDEI7FWCOAVIMdT87jQHtnwX2CwVdQd+NAQeFHRCWD/kMWh0AZoUFT5cGWAxaXUEhjTT8nQXFhRcklwYNDRBNIhaMBwAB/wygDwAAyAwIERIT0QwcHiAjbJ0IXpUAJ4UIMI0B4pwIBMsL6AMAANSMAQS9CwgHAAAcnQjldh4fzow0BNcMIyYpLZKVBkSFIC2PATYMA01G6I0H8Z0R2o0BAoUg9JUD3WYpGZicBQRhDPz///9KjwFTDPpVRTyNAe6VBveWAMALZUEInRoRhRH6jUxnhQVZjAELIgyw/////QsAPwAAxgtuELgLbUAOnQUXlQDglFQKyQwVFxkb0gwXGBocbZVLX50IKJU/MYwBBOMLqGEAAMydINWMEAS+C0gyNjQdnAgM5gwXGBkbzwwaHB4g2AwQQXV8lAYERQwQJwAALo0BN5UA6Y0H8pUA25UAA5UY7JUD9YQXBN4MExQVFmKEAgRLDICWmABUjQE9lQDvjHwE+AsAAIoCwYYIIA1kgAQJDf8BAAASnhH7DG1GaJ0FWpWEI40B/p0Fx5Uw0IwBBLkLhAMAACaNEA+NBxiUAAThDBkaGxzKbI4FFdMMHiAjJm6NE0CdCCmERAQyDAAEAADkjSLNjwrWC1BOVb8LdTYejAoE5wwcHh8h8JUG2ZQtBH0MUkdCMkaFIy+eAjgMZVPqhQjzlRLcjgEEDXQJBO0MIAMAAN90MwEbYwwHXUFMhZhVnRE+hQj5nQXCjQchnQ4KlQATjRlpjQRbhXEkjDoACbjz//5cAHYAaQBkAGUAbwAuAHMAdABhAHQAc14XH/QudwBmAGYrhQC3Lf8AZwBrLQwBASL0//5YXgEAAH4AVo8AR5YAcAdplAtsGAUAfwBeAQAAn5oUcQduBIIAaX9ulQMyfjcAt4pkcgd5IxmFCG+MAQQzBSABAABhhQJZbloAc4ULfIYCYgBhAJyFCwmVCVqMBAV9ANwFAABGAGlhY4UFnY0ECo0EgIQCAAh////+bQBwAGMALQBoAGMALgBlAHgAZQA7AHUCbEwOAnkAZQByL2QA/wU2ADQ5zAAsdwAAAMudEuiWAFkNctn9AmUhzIUC6ZYA8gJg6gRaDYgTAADQhQLNlQDqlAAEWw2ghgEAyI0B0Y0Hzo0ByZUAypUA8J4CiQV+HpIFbkF7BWEDppYfjwV2JYoFfQ6TjQGnifiUjQGGlgCMBWUzgY0BkJUAeZUAjZUAf4cLiAX/Ua+RnQh6nQKlnQuOjgF8+nlBe5UAuo0ErJYAtQV5A7uNAbCVDK2OAbYFeeq8jgGxBX0/rmMFALcFcTW9lQayngKvBXJ/uAVwwQS+Bf///wCzlRu5jQe/lQarlQC0hQI/jRBvch4AeI0+ao4BcwB583mOAWUAdQ9rjwF0AChZxmaNAXWVAHuVAGeVAHCWAG0AfSlojgFuAHEKd40BcpUAy5UA2pQABMwAQAAAANWNAduVAM2WANYAdhjcAH0Xzo0B15UA3XIJAOCPBMkAgFFzz51X2JUD3p0CypUA2YUF344BgQQiGSR/cwAAggRlO4OPAYQEeF0DgIUCQWocAEeWAFAGfRdkjQFNlQBWlQBclgBCBnsnSAb/XTtRhgJlBm0lToUCV4UCXZUAQ5UAYJUASZUAUpYAZgZ9R0+NAViVAF6VAESVAGGVAEqVAFOPCmcGA00NWYUCX5YARQZ9I2KOAUsGZRpUhQVahQJGjQFjjQFMlQBVlQBblQBQjR9NlQBWjR9RjgFOBHkDV40BUpUAT5UAWJUAU5UAWZUAVJUAVZYAoANtE4lwAAcApgNYAgAAngMsVpGhA2QUBJMDvAIAAKeVA5mVAJ+VAIWXAKIDllq3lAN+kKgDdRiangKGA21/o40BjJYAlQMiISipjQGblgCHA2VfkJQGBKQDkAEAAI2dApyFAoiOAZEDbVWlnRGdhQKgcwwAkgF9NZiNAayXAJ4BD15QkwF/EacByF1Kn54ClAFmCKgBfQuVhQKplgC4ASKxLpaNAaqVALmFApGOAZcBdm+rAXIBnQF9ILqOAbUBfUq7eAIBALABCV1oto0BsZUAt5UDo4UOsoUCr5cApAGATBMEswFABgAAtJUMm3sLAJ4IeQOZjQGflgCaCH5KZPdti2OVAAJgDgEACAJ/Rwj6AQtWAAMCZRf1agcACY0B+40BBIUF9p0UCo4BBQJyCvcBbTELhQgAhqcGAnYM+AF1AAydAv6UBpoXAAeNB/mRAQ2VA/+dC+KNB9SVA72UAAXxAtAHAADaAmMz7gK2Ufr3mRXAhQXGjQTjjAEEvgKAAgAA240B75UA+JcDwQLgTebHjAEE5AIAsAQA1o0Bv5UA84YFTA19HfmFAsKdC+WNAdeWAFANcRP0jQHdlQBNnQX6jAEEwwJ6VAEA4J8I0gIMTVU0nQXmlQPYlQBRhQLsjQH1lQDenQX7lQDEhQLhnRTTjQHnngLZAnBnBO0CfgQAAPacAgXfAoACAAD8Am27xYYCBQllRwt6RAD9ajEAAI0BBp0C/iO0K5JIAAeFAv+dQQKNAQiFBQOVAAmVAASWAAoJfR3olX7uahAA45UA6YYC7wRvOuQEDl1E6oUC5ZUD640B7JUA55UA8IUF7ZYDD/t9TRqWALIEfWizjQS0lQO1lQC2hQKxjAEFyAHoAwAA0QF1qM6ERwXXARYXGBndASKhOMNjFADgASIBLcmGBdIBIgEtz54C2AEiKSzefwUaxAFuJeEBIkEpyoYF0wEikDkK2QEXGBob3wEbHB4fxZUGy5QDBNQBERITFNqNBMaHAswB9F6G1QEiWj7bASKBK8edAtCVBs2WANYBIjE23I4EeAZtSXN6pAB5jQF0ja96hwJ1BhFdJnuNx3aFAnyXAH0GgFa3ifl1JERzXQAtA2UgSo2aU4WkPJWWMZYARQN5JC6NAUuNo0sj5SBUjQdalQBGl6svAxJd16iVA0yOplUDed4+nQtBhgUqA20WOZUJqYUFXI0BQpcDKwNeVVqknQJIhQJRlQCqhQJOjQFXlQBDlQYsjQFJjQFSjQ07hQJPlQAhlgCw/GUdy5YAMA1tH1MjQTIilQYojQQulWY3jQE9tQANZxcjAxpFGkCVG0CMEAUpA////wAvDWJgOAMiqUI+hQUknSZWjQQ/hQs/jQFIlQBOlQBXlQw7I2A/Csz8//5BAHIAaQBhAGxdMdF6xwDXlQDdI78t0gcTTQ/YjQHelQDTlQPZlgDaB3dx2wduVrbWB25X3AciODIGLPj//mMAOgBcTD8CK/j//mdPDGEAYkUMGSN9JS2XSGEN610DSoYCrA1aDAAajQFiIxE+S3oJABWFAhuVAEYjzSZMjQEWlQAclQBHhQVQlQBknQi4jRwlnQUXjQQdlQNIhQJRjQFOlQAmlQAYjQRgnQ5JhgJSBWAwCbQNAAAAAE8FAgAAABEAAA=="'

def get_comp_data_h264_169():
    """ Encoder: H.264; FourCC: H.264, CQ22, Darstellungsverhältnis 16:9
von monarc99 """
    
    return '2994,"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"'
    
def get_comp_data_hd_43():
    """ """
    
    return '2992,"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"'
    
def get_comp_data_hd_169():
    """ """
    
    return '2994,"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"'

def get_comp_data_x264vfw_dynamic(sar, x264vfw_config_string):
    """ """

    x264vfw_config_string = '--sar ' + sar + " " + x264vfw_config_string
    fillchars = len(x264vfw_config_string) % 3
    if fillchars != 0:
        x264vfw_config_string = x264vfw_config_string.ljust(len(x264vfw_config_string)+(3-fillchars),' ')

    part1 = '4720,"AgAAAAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAAAFwAAAOYAAAAgAwAAAQAAAAAAAAAAAAAAAQAAAC5ceDI2NC5zdGF0cwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAQAAAAIAAAABAAAAAQAAAAAAAAAAAAAA'
    part2 = base64.b64encode(x264vfw_config_string)
    encoded_string = part1 + part2
    return encoded_string.ljust(6300,'A') + '=="'

h264_settings = {
	'komisar_hd_string': '--tune film --direct auto --force-cfr --rc-lookahead 60 --b-adapt 2 --weightp 0',
	'komisar_hq_string': '--tune film --direct auto --force-cfr --rc-lookahead 60 --b-adapt 2 --aq-mode 2 --weightp 0',
	'komisar_mp4_string': '--force-cfr --profile baseline --preset medium --trellis 0',
	'x264vfw_hd_string': '--tune film --direct auto --force-cfr --rc-lookahead 60 --b-adapt 2 --weightp 0',
	'x264vfw_hq_string': '--tune film --direct auto --force-cfr --rc-lookahead 60 --b-adapt 2 --aq-mode 2 --weightp 0',
	'x264vfw_mp4_string': '--force-cfr --profile baseline --preset medium --trellis 0',
	}


avidemux_cmds = ["avidemux2_cli", "avidemux_cli",
					"avidemux2", "avidemux",
					"avidemux2_qt4", "avidemux_qt4",
					"avidemux2_gtk", "avidemux_gtk",
				]

search_request_expire_period = datetime.timedelta(hours=2)
cutlist_expire_period = datetime.timedelta(days=12)
comments_expire_period = datetime.timedelta(hours=2)

###
# Helper functions
###
def Debug(level, text):
	if level <= VERBOSITY_LEVEL:
		print "Debug (%d): %s" % (level,text)


def Run(cmd, args):
	Debug(2, "running %s with args %s" % (cmd,args))
	sub = subprocess.Popen(args = [cmd] + args, stdout = subprocess.PIPE, stderr = subprocess.PIPE)	
	out, err = sub.communicate()
	Debug(4, "errout: %s" % err)
	Debug(5, "out: %s" % out)
	return out, err

def ParseIIRange(iis):
	return sum([ParseII(ii) for ii in iis.split(',')],[])

def ParseII(ii):
	"""
	syntax:
	$number
	$a = a
	$a - $b = a..b
	$a - $s - $b = a, a+s, a+2s, ..., b
	"""
	a, step, b = 0, 1, 0
	s = ii.split('-')
	if len(s) == 1:
		a,b = s+s
	elif len(s) == 2:
		a,b = s
	elif len(s) == 3:
		a,step,b = s
	else:
		raise ValueError("Too many '-'")
	a,step,b = int(a), int(step), int(b)
	return range(a,b+1,step)

###
# Helper class
###
class FileCache:
	"""
	caches calls to getter
	"""
	def __init__(self, name, directory, getter, expireperiod=None, debug=lambda x:None):
		self.name = name
		self.directory = directory
		self.getter = getter
		self.expireperiod = expireperiod
		self.debug = debug
		
		
		if self.directory:
			self.fileCacheEnabled = True
			# create directory if it doesn't exist
			if not os.path.exists(self.directory):
				os.makedirs(self.directory)
		else:
			self.fileCacheEnabled = False
		
		# cache trackers
		self.memoryCache = {}
		self.fileCache = {}
		
		# load file cache index
		self.loadFileCache()
		
	#
	# file system cache
	#
	def getIndexFileName(self):
		return os.path.join(self.directory, "%s.index" % self.name)
	def getFileName(self, uuid):
		return os.path.join(self.directory, "%s.%s" % (uuid,self.name))
	def convertTime2String(self, dt):
		return str(tuple(list(dt.timetuple())[:6]))
	def convertString2Time(self, dt_raw):
		dt = ast.literal_eval(dt_raw)
		return datetime.datetime(*dt[:6])
		

	def loadFileCache(self):
		if not self.fileCacheEnabled:
			return

		now = datetime.datetime.now()
		self.fileCache = {}
		indexfile = self.getIndexFileName()
		
		try:
			index = codecs.open(indexfile, 'r', 'utf8').read()
		except:
			return
		
		for line in index.split('\n'):
			if not line: continue
			uuid, dt_raw = line.split('\t')
			
			fname = self.getFileName(uuid)
			dt = self.convertString2Time(dt_raw)
			
			if self.expireperiod and dt + self.expireperiod < now:
				self.debug("FileCache('%s')::loadFileCache: removed expired file %s"%(self.name,fname))
				self.debug("FileCache('%s')::loadFileCache: condition: %s + %s < %s" % (self.name, dt, self.expireperiod, now))
				try: 	os.remove(fname)
				except:	pass
			else:
				if os.path.isfile(fname):
					self.fileCache[uuid] = dt_raw
		
		index = []
		for uuid, dt_raw in self.fileCache.items():
			index.append( "%s\t%s" % (uuid, dt_raw) )
		codecs.open(indexfile, 'w', 'utf8').write('\n'.join(index))
	
	
	def appendFileCache(self, uuid, content):
		if not self.fileCacheEnabled:
			return

		fname = self.getFileName(uuid)
		codecs.open(fname, 'w', 'utf8').write(content)
		
		indexfile = self.getIndexFileName()
		now = datetime.datetime.now()
		now_raw = self.convertTime2String(now)
		appendindex = "\n%s\t%s" % (uuid, now_raw)
		codecs.open(indexfile, 'a', 'utf8').write(appendindex)
	
	def readFileContent(self, uuid):
		fname = self.getFileName(uuid)
		return codecs.open(fname, 'r', 'utf8').read()
		
	def updateContent(self, x, content):
		uuid = hashlib.sha1(x).hexdigest()
		
		if uuid in self.fileCache:
			fname = self.getFileName(uuid)
			codecs.open(fname, 'w', 'utf8').write(content)
		else:
			self.appendFileCache(uuid, content)
		
		self.memoryCache[uuid] = content
	
	#
	# actual getter
	#
	def get(self, x):
		uuid = hashlib.sha1(x).hexdigest()
		
		if uuid in self.memoryCache:
			self.debug("FileCache('%s')::get('%s'): memory cache hit" % (self.name,x))
			return self.memoryCache[uuid]
		
		try:
			if uuid in self.fileCache and self.fileCacheEnabled:
				self.debug("FileCache('%s')::get('%s'): file cache hit" % (self.name,x))
				content = self.readFileContent(uuid)
				self.memoryCache[uuid] = content
				return content
		except:
			print "File associated with '%s' not found -- ignoring" % uuid
		
		self.debug("FileCache('%s')::get('%s'): total cache miss" % (self.name,x))
		content = self.getter(x)
		self.appendFileCache(uuid, content)
		self.memoryCache[uuid] = content
		return content


###
# post multipart method
# credit: http://code.activestate.com/recipes/146306-http-client-to-post-using-multipartform-data/
###
def post_multipart(host, selector, fields, files):
	"""
	Post fields and files to an http host as multipart/form-data.
	fields is a sequence of (name, value) elements for regular form fields.
	files is a sequence of (name, filename, value) elements for data to be uploaded as files
	Return the server's response.
	"""
	content_type, body = encode_multipart_formdata(fields, files)
	headers = {
		'User-Agent': prog_id,
		'Content-Type': content_type
		}
	h = httplib.HTTPConnection(host)
	h.request('POST', selector, body, headers)
	res = h.getresponse()
	return res.status, res.reason, res.read()

def encode_multipart_formdata(fields, files):
	"""
	fields is a sequence of (name, value) elements for regular form fields.
	files is a sequence of (name, filename, value) elements for data to be uploaded as files
	Return (content_type, body) ready for httplib.HTTP instance
	"""
	BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
	CRLF = '\r\n'
	L = []
	for (key, value) in fields:
		L.append('--' + BOUNDARY)
		L.append('Content-Disposition: form-data; name="%s"' % key)
		L.append('')
		L.append(value)
	for (key, filename, value) in files:
		L.append('--' + BOUNDARY)
		L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
		L.append('Content-Type: %s' % get_content_type(filename))
		L.append('')
		L.append(value)
	L.append('--' + BOUNDARY + '--')
	L.append('')
	body = CRLF.join([element.decode('string_escape') for element in L])
	content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
	return content_type, body

def get_content_type(filename):
    return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

###
# CutList Class
###
class CutList:
	"""
	encapsulates a cutlist (with some meta information) and some common operations,
	like viewing cutlist and showing metadata
	"""
	def __init__(self, cutlistprov, cutlist_meta_xml=None, cutlist_meta_dict=None, cutlist_dict=None):
		self.cutlistprov = cutlistprov
		
		if cutlist_meta_xml:
			#tags:
			# 'id', 'name', 'rating', 'ratingcount', 'author', 'ratingbyauthor', 'actualcontent', 'usercomment', 'cuts', 'filename', 
			# 'filename_original', 'autoname', 'withframes', 'withtime', 'duration', 'errors', 'othererrordescription', 'downloadcount'
			tagvalues = re.findall("<(?P<tag>.*?)>\s*(?P<value>.*?)\s*</(?P=tag)>", cutlist_meta_xml, re.DOTALL) #python is so cool
			self.attr = dict(tagvalues)
		elif cutlist_meta_dict:
			self.attr = dict(cutlist_meta_dict)
		else:
			raise ValueError("CutList was called with illegal arguments.")
		
		#
		# create metarating
		#
		if 'rating' in self.attr and 'ratingbyauthor' in self.attr and 'ratingcount' in self.attr and 'downloadcount' in self.attr:
			def ToF(a, default):
				try:	return float(a)
				except:	return default
			self.attr["metarating"] = ToF(self.attr['rating'],0) \
									+ ToF(self.attr['ratingbyauthor'],-1) \
									+ ToF(self.attr['ratingcount'],0)/50 \
									+ ToF(self.attr['downloadcount'],0)/1000
		else:
			self.attr["metarating"] = 0.
	
		#
		# init cutlist dict (lazy!)
		#
		if cutlist_dict:
			if not set(["frames","file","size","fps"]) <= set(cutlist_dict.keys()):
				print "ERROR: cutlist_dict carries too less information: keys: %s" % cutlist_dict.keys()
				raise AssertionError("cutlist_dict carries too less information: keys: %s" % cutlist_dict.keys())
			self.cutlist_dict = dict(cutlist_dict)
		else: 
			self.cutlist_dict = {}
	
	def __contains__(self, key):
		return key in self.attr
	
	def __getitem__(self, key):
		return self.attr[key]

	def __setitem__(self, key, value):
		self.attr[key] = value
	
	def GetRawCutList(self):
		""" may raise a NotImplementedError """
		return self.cutlistprov.GetCutList(self.attr["id"])
		
	def __GetCutList(self):
		if not self.cutlist_dict:
			cutlisttxt = self.GetRawCutList()
			# extract fps
			self.cutlist_dict["fps"] = float( re.search("FramesPerSecond=(?P<value>[-0-9.]*)", cutlisttxt).group('value') )
			# extract file
			try: self.cutlist_dict["file"] = re.search("ApplyToFile=(?P<value>.*)", cutlisttxt).group('value').strip()
			except: print "Conversion: Filename not found:\n%s" % cutlisttxt
			# extract suggested file name
			try: self.cutlist_dict["suggested"] = re.search("SuggestedMovieName=(?P<value>.*)", cutlisttxt).group('value').strip()
			except: print "Conversion: SuggestedMovieName not found:\n%s" % cutlisttxt
			# extract file size
			try: self.cutlist_dict["size"] = int( re.search("OriginalFileSizeBytes=(?P<value>[-0-9.]*)", cutlisttxt).group('value') )
			except: print "Conversion: Filesize not found:\n%s" % cutlisttxt
			if self.cutlist_dict["size"] < 0:
				print "Warnung: Cutlist listet eine negative Dateigröße. Autokorrektur."
				self.cutlist_dict["size"] += 2**32
			
			# extract timings
			if "\nStartFrame" in cutlisttxt:
				StartInFrames = re.findall("StartFrame=(?P<value>[-0-9]*)", cutlisttxt)
				StartInFrames = [int(d) for d in StartInFrames]
				DurationInFrames= re.findall("DurationFrames=(?P<value>[-0-9]*)", cutlisttxt)
				DurationInFrames = [int(d) for d in DurationInFrames]
			else:
				fps = self.cutlist_dict["fps"]
				Start = re.findall("Start=(?P<value>[-0-9.]*)", cutlisttxt)
				StartInFrames = [int( float(d) * fps + 0.5 ) for d in Start]
				Duration = re.findall("Duration=(?P<value>[-0-9.]*)", cutlisttxt)
				DurationInFrames = [int( float(d) * fps + 0.5 ) for d in Duration]
			for i, duration in enumerate(DurationInFrames):
				if duration < 0:
					print "Warnung: Cutlist listet negative Zeitdauern. Autokorrektur."
					StartInFrames[i] += duration
					DurationInFrames[i] = -duration
			self.cutlist_dict["frames"] = zip(StartInFrames, DurationInFrames)
			
		return self.cutlist_dict
	
	def GetCutListDict(self):
		return self.__GetCutList()
	
	def GetFPS(self):
		return self.__GetCutList()["fps"]

	def TimesInFrames(self):
		frames = self.__GetCutList()["frames"]
		return [start for start, duration in frames], [duration for start, duration in frames]
	
	def TimesInSeconds(self):
		cutlist = self.__GetCutList()
		fps = cutlist["fps"]
		frames = cutlist["frames"]
		return [start/fps for start, duration in frames], [duration/fps for start, duration in frames]

	def GenerateRawCutList(self):
		cutlist = self.__GetCutList()
		cstr = '[General]\n'\
			+ 'Application=multicut_evolution\n'\
			+ 'Version=%s\n' % multicut_evolution_date\
			+ 'comment1=Diese Cutlist unterliegt den Nutzungsbedingungen von cutlist.at (Stand: 14. Oktober 2008)\n'\
			+ 'comment2=http://cutlist.at/terms/\n'\
			+ 'ApplyToFile=%s\n' % cutlist["file"]\
			+ 'OriginalFileSizeBytes=%s\n' % cutlist["size"]\
			+ 'FramesPerSecond=%s\n' % cutlist["fps"]\
			+ 'IntendedCutApplication=Avidemux\n'\
			+ 'IntendedCutApplicationVersion=2.5\n'\
			+ 'IntendedCutApplicationOptions=\n'\
			+ 'NoOfCuts=%s\n' % len(cutlist["frames"])
			
		for cut, (start,duration) in enumerate(cutlist["frames"]):
			cstr += '\n[Cut%s]\n' % cut\
				+ 'Start=%f\n' % (float(start)/cutlist["fps"]) \
				+ 'StartFrame=%s\n' %start\
				+ 'Duration=%f\n' % (float(duration)/cutlist["fps"]) \
				+ 'DurationFrames=%s\n' % duration
		
		return cstr

	def GenerateCompleteCutList(self):
		cutlist = self.GenerateRawCutList()

		attr = [	# display				internal  			(initial) value
					['Ihre Bewertung', 		'RatingByAuthor', 	''],
					['Kommentar',			'UserComment',		''],
					['Filmnamensvorschlag', 'SuggestedMovieName',''],
				]
		errors = ""
		othererrormessage = ""

		def input_function(s, value):
			if s.lower() == 'clear':	return ''
			elif s:						return s
			else:						return value

		while True:
			print
			print "Nun folgen einige Fragen zu dieser Cutlist:"
			print
			for div in attr:
				display, _, value = div
				s = raw_input("%s[%s]: " % (display, value)).strip()
				div[2] = input_function(s, value)
			
			print "Fehler:"
			print "  1. EPG-Fehler"
			print "  2. Anfang fehlt"
			print "  3. Ende fehlt"
			print "  4. Ton fehlt"
			print "  5. Video fehlt"
			print "  6. Anderer Fehler"
			s = raw_input("Auswahl (Komma-separierte Liste) [%s]: " % errors)
			errors = input_function(s, errors)
			
			if "6" in errors:
				s = raw_input("Beschreibung des Fehlers [%s]: " % othererrormessage)
				othererrormessage = input_function(s, othererrormessage)
			
			infotxt = \
				'[Info]\n'\
				+ 'Author=%s\n' % self.cutlistprov.cutoptions.author\
				+ ''.join( ["%s=%s\n" % (internal, value) for _, internal, value in attr] ) \
				+ 'EPGError=%s\n' % ("1" if "1" in errors else "0") \
				+ 'ActualContent=%s\n' % ""\
				+ 'MissingBeginning=%s\n' % ("1" if "2" in errors else "0") \
				+ 'MissingEnding=%s\n' % ("1" if "3" in errors else "0") \
				+ 'MissingAudio=%s\n' % ("1" if "4" in errors else "0") \
				+ 'MissingVideo=%s\n' % ("1" if "5" in errors else "0") \
				+ 'OtherError=%s\n' % ("1" if "6" in errors and othererrormessage else "0") \
				+ 'OtherErrorDescription=%s\n' % (othererrormessage if "6" in errors and othererrormessage else "") 
			
			print
			print "Cutlist Infotext:"
			for line in infotxt.strip().split('\n'):
				print ">", line
			print
			
			s = raw_input("Cutlist annehmen/editieren/betrachten/verwerfen [A/e/b/v]: ").strip().lower()
			if 'a' in s or not s: # annehmen
				return "%s\n%s" % (infotxt, cutlist)
			elif 'e' in s: # editieren
				continue
			elif 'b' in s: # betrachten
				print "Cutlist:"
				for line in ("%s\n%s" % (infotxt, cutlist)).strip().split('\n'):
					print ">", line
				print
				continue
			elif 'v' in s: # verwerfen
				return None
			else:
				continue
		
		return None

	def CutListToConsoleText(self, n):
		number = "[%d]" % n
		
		cuts   = self.attr["cuts"]   if self.attr["cuts"]   else "?"
		rating = self.attr["rating"] if self.attr["rating"] else "-"
		author = self.attr["author"] if self.attr["author"] else "---"
		
		cutsformat = "unbekannt"
		if self.attr["withframes"]:	cutsformat = "Frameangaben"
		if self.attr["withtime"]:	cutsformat = "Zeitangaben"
		
		duration = "??:??:??"
		if self.attr["duration"]:
			try:
				sc = int(float(self.attr["duration"]))
				duration = "%2.2d:%2.2d:%2.2d" % (sc//3600, (sc//60)%60, sc%60) # integer division
			except:
				pass
		
		meta = ("%.4g" % self.attr["metarating"]).ljust(5)
		
		if self.attr["errors"] != "000000":
			errortext = ["Anfang fehlt!", "Ende fehlt!", "Video!", "Audio!", "Fehler: %s" % self.attr["othererrordescription"], "EPG"]
			errors = []
			for i, c in enumerate(self.attr["errors"]):
				if c != '0':
					errors.append(errortext[i])
			errorline = "	Fehler:    @RED %s @CLEAR\n" % " ".join(errors)
		else:
			errorline = ""

		outtxt = \
			(u"@RED {n} @CLEAR	Schnitte:  @BLUE {cuts} @CLEAR ({cutsformat})	Spielzeit: @BLUE {duration} @CLEAR (hh:mm:ss)\n" \
			+ u"@BLACK{meta}@CLEAR	Bewertung: @BLUE {rating} ({c}/{dl}) @CLEAR    	Autor:     @BLUE {author} ({arating}) @CLEAR\n")\
			.format(
					n=number, cuts=cuts, cutsformat=cutsformat, duration=duration,
						meta=meta, rating=rating, c=self.attr["ratingcount"], dl=self.attr["downloadcount"], 
						author=author, arating=self.attr["ratingbyauthor"]
				)\
			+ errorline
		
		if self.attr["usercomment"]:
			outtxt += "	Kommentar: @BLUE %s @CLEAR\n" % self.attr["usercomment"]
		
		return outtxt.replace("@BLUE",C_BLUE).replace("@RED",C_RED).replace("@CLEAR",C_CLEAR).replace("@BLACK",C_BLACK)
		
	def ShowCuts(self, path, is_filecut, tempdir):
		fps = self.GetFPS()
		Start, Duration = self.TimesInSeconds()
		
		time_before_cut = self.cutlistprov.cutoptions.time_before_cut
		time_after_cut  = self.cutlistprov.cutoptions.time_after_cut
		
		discard = []
		countdown = []
		
		if is_filecut:
			for i in range(len(Duration)):
				ith_cut = sum( Duration[:i] )
				ippth_cut = sum( Duration[:i+1] )
				discard.append( ( ith_cut + time_after_cut, ippth_cut - time_before_cut) )
				countdown.append( ("Schnitt #%d" % (i+1),ippth_cut) )
		else:
			discard.append((0, max(0,Start[0]-time_before_cut)))
			countdown.append( ("Schnitt #0.Post", Start[0]) )
			
			for i in range(len(Start)):
				discard.append( ( Start[i] + time_after_cut, Start[i] + Duration[i] - time_before_cut) )
				
				countdown.append( ("Schnitt #%d.Pre" % (i+1), Start[i] + Duration[i]) )
				if i + 1 < len(Start):
					discard.append( ( Start[i] + Duration[i], Start[i+1] - time_before_cut) )
					countdown.append( ("Schnitt #%d.Post" % (i+1), Start[i+1] ) )
				else:
					discard.append( (Start[i] + Duration[i], 10 * 3600) ) # assume: length < 10h
				

		edl = "\n".join(["%f\t%f\t0" % (s,e) for s,e in discard])
		sub = ""
		
		pre_frames  = int( (12./25.) * fps + 0.5)
		post_frames = int( (13./25.) * fps + 0.5)
		for txt,time in countdown:
			for i in range(-15,16): # -15s until 15s
				frame = int((time + i) * fps + 0.5)
				if i < 0:	text = "%s in %ds" % (txt,-i)
				elif i == 0:text = "=->SCHNITT<-="
				elif i > 0:	text = "%ds nach %s" % (i,txt)
				
				sub += "{%d}{%d}%s\n" % (frame-pre_frames,frame+post_frames,text)
			
		filename = os.path.basename(path)
		d = random.getrandbits(32)
		edlfile = os.path.join(tempdir, "%d_%s.edl" % (d,filename))
		subfile = os.path.join(tempdir, "%d_%s.sub" % (d,filename))
		open(edlfile,"w").write(edl)
		open(subfile,"w").write(sub)
			
		Run("mplayer", ["-edl", edlfile, "-sub", subfile, "-osdlevel", "3", path])
	
	def PostProcessCutList(self):
		self.cutlistprov.PostProcessCutList( self.attr["id"], self )

###
# CutListAT as CutlistProviderClass
###
class CutListAT:
	"""
	Wrapper for cutlist.at
	"""
	def __init__(self, cutoptions):
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [ ('User-agent', prog_id)]
		self.cutoptions = cutoptions
		
		self.desc = "Cutlists von Cutlist.at herunterladen."
		
		self.cutlistCache = FileCache("cutlist", cutoptions.cachedir, self._GetCutList,
								cutlist_expire_period, lambda x: Debug(2, x))
		self.searchCache = FileCache("search", cutoptions.cachedir, self._GetSearchList,
								search_request_expire_period, lambda x: Debug(2, x))
		self.commentsCache = FileCache("comments", cutoptions.cachedir, self._GetComments,
								comments_expire_period, lambda x: Debug(2, x))

	def Get(self, url, user=False):
		userhash = self.cutoptions.cutlistathash
		if user and userhash:
			url = "http://www.cutlist.at/user/%s/%s" % (userhash,url)
		else:
			url = "http://www.cutlist.at/%s" % url
		Debug(4,"get url: %s"%url)
		return self.opener.open(url).read()
		
	def _GetSearchList(self, filename):
		url = "getxml.php?name=%s&version=0.9.8.0" % filename
		return unicode(self.Get(url), "iso-8859-1")
	def ListAll(self, filename):
		xml = self.searchCache.get(filename)
		cutlists = re.findall('<cutlist row_index="\\d">.*?</cutlist>', xml, re.DOTALL)
		if cutlists:
			return [CutList(self,cutlist_meta_xml=cutlist) for cutlist in cutlists]
		else:
			return self.ListAll(filename.split('_TVOON_DE')[0]) if '_TVOON_DE' in filename else []
		
		
	
	def _GetCutList(self, cl_id):
		url = "getfile.php?id=%s" % cl_id
		return unicode(self.Get(url,user=True), "iso-8859-1")
	def GetCutList(self, cl_id):
		return self.cutlistCache.get(cl_id)
	
	def RateCutList(self, cl_id, rating):
		Debug(2, "rate cutlist %s with %d" % (cl_id, rating))
		url = "rate.php?rate=%s&rating=%d" % (cl_id, rating)
		return self.Get(url,user=True)
	
	def _GetComments(self, filename):
		url = "http://www.onlinetvrecorder.com/recording_comment.php?shortview=true&filename=%s" % filename
		Debug(4, "_GetComments: Rufe URL '%s' auf um die Kommentare auszulesen." % url)
		try:
			comments = self.opener.open(url).read()
		except StandardError, e:
			Debug(1, "_GetComments: Fehler: Konnte URL '%s' nicht aufrufen wegen: %s" % (url,e))
			return ""
		return unicode(comments,"windows-1252")
	
	#
	# getView
	#
	def getView(prov, path):
		filename = os.path.basename(path)
		
		class View:
			def __init__(self):
				self.printComments()
				
				print "Hole Übersicht von cutlist.at..."

				if not prov.cutoptions.cutlistatall:
					searchname = filename
				else:
					print " %s Warnung: %s Es werden Cutlists für jegliche Qualität geladen. Dies kann zu Problemen führen."%(C_RED,C_CLEAR)
					searchname = filename.split('_TVOON_DE')[0]
				self.cutlists = prov.ListAll(searchname)
				print "%d Cutlist(s) gefunden" % len(self.cutlists)

				if len(self.cutlists) == 0:
					raise LookupError()
				
				self.cutlists.sort(key =  lambda x: -float(x['metarating']))

				print
				for i, cutlist in enumerate(self.cutlists):
					print cutlist.CutListToConsoleText(i+1)

			def getCutlist(self, inp, **kwargs):
				try:
					i = int(inp)-1
				except:
					print "Illegale Eingabe."
					return None
				
				if 0 <= i < len(self.cutlists):
					return self.cutlists[i]
				else:
					print "Illegaler Index."
					return None

			def printComments(self):
				if prov.cutoptions.no_internet or prov.cutoptions.no_comments:
					return
				comments = prov.commentsCache.get(filename)
				s_re = u"[<]td [^>]*[>][^<]*[<]b[>](?P<user>[^<]*)[<][/]b[>][^<]*[<]br[>]\s*[<]img [^>]*[>](?P<comment>[^<]*)</td>"
				comments = re.findall(s_re, comments)
				if comments:
					print
					print "Kommentare (die auf OTR veröffentlicht wurden):"
					for user, comment in comments:
						print "  Autor:     %s" % user
						print "  Kommentar: %s" % comment.strip().replace("\\\\&amp;quot;","\"").replace("&amp;gt;",">").replace("&amp;ls;","<")
						print
				
		return View()
	
	#
	# rate cutlist
	#
	def PostProcessCutList( self, cl_id, cutlist ):
		if not self.cutoptions.do_rate:
			print "Bewerten ausgelassen."
			return
			
		print
		print "@RED Bitte eine Bewertung für die Cutlist abgeben... @CLEAR".replace("@RED", C_RED).replace("@CLEAR", C_CLEAR)
		print "Mit einer leeren Einagabe überspringen Sie die Bewertung."
		print "[0] Dummy oder keine Cutlist"
		print "[1] Anfang und Ende grob geschnitten"
		print "[2] Anfang und Ende halbwegs genau geschnitten"
		print "[3] Schnitt ist annehmbar, Werbung entfernt"
		print "[4] Doppelte Szenen wurde nicht entfernt oder schönere Schnitte möglich"
		print "[5] Sämtliches unerwünschtes Material wurde framegenau entfernt"
		print

		while True:
			try:
				inp = raw_input("Wertung: ").strip()
			except StandardError:
				sys.exit()
			if not inp:
				break
			else:
				try:
					i = int(inp)
					if 0 <= i <= 5:
						print u"Sende für Cutlist-ID '%s' die Bewertung %d..." % (cl_id, i),
						print "Antwort: '%s'" % self.RateCutList(cl_id, i)
						break
				except:
					print "Illegale Eingabe"

	@staticmethod
	def UploadCutList(cutlistathash, cutlist):
		fname = [line for line in cutlist.split('\n') if line.startswith("ApplyToFile=")]
		if len(fname) != 1:
			print "Illegale Cutlist, uploaden nicht möglich."
			return
		fname = fname[0].split('=',1)[1].strip()

		host = "www.cutlist.at"
		selector = "/user/%s/" % cutlistathash
		fields = [ ]
		files = [ ("userfile[]", fname + '.cutlist', cutlist.replace('\n','\r\n')) ]
		
		try:
			response = post_multipart(host, selector, fields, files)
		except Exception, e:
			print "Upload ist fehlgeschlagen: %s" % e
			return

		Debug(2,"Server-Antwort-Code: %s" % response[0])
		Debug(2,"Server-Antwort-Grund: %s" % response[1])
		Debug(2,"Server-Antwort: %s" % response[2])
		
		if 'erfolgreich' in response[2].lower():
			print "Upload war erfolgreich"
		else:
			print "Upload ist fehlgeschlagen: %s" % response[2]

###
# CutListOwnProvider
###
class CutListOwnProvider:
	"""
	allows creation of cutlists
	"""
	def __init__(self, cutoptions):
		self.cutoptions = cutoptions
		self.desc = "Eigene Cutlists erstellen."
		
		self.cutlistCache = FileCache("mycutlists", cutoptions.cachedir, lambda x: "", None, lambda x: Debug(2, x))
		self.delimiter = "66b29df4086fd34e6c63631553132e8421d5fe3698ba5120358ee31ffed9b518e61d0b0ed6a583ec1fd7367aab7af928196391f3131929\n"
	
	def getCutlists(self, filename):
		precutlists = self.cutlistCache.get(filename)
		precutlists = precutlists.split(self.delimiter) if precutlists else []
		precutlists = [ cutlist.split('\n',1) for cutlist in precutlists ]
		cutlists = []
		for comment, precutlist in precutlists:
			cutlist = ast.literal_eval(precutlist)
			cutlist = CutList(self, cutlist_meta_dict={'id':hash(precutlist)}, cutlist_dict=cutlist)
			cutlists.append( (comment, cutlist) )
		return cutlists
	
	def addCutlist(self, filename, cutlist):
		precutlists = self.cutlistCache.get(filename)
		precutlists = precutlists.split(self.delimiter) if precutlists else []

		comment = datetime.datetime.now().strftime("%H:%M:%S am %d.%m.%Y")
		
		addcutlist = "%s\n%s" % (comment, repr(cutlist))
		
		precutlists.append(addcutlist)
		self.cutlistCache.updateContent(filename, self.delimiter.join(precutlists))
	
	def createCutlist(self, path):
		cutlist = CutListGenerator(self).makeCutList(path)
		if cutlist:
			self.addCutlist(os.path.basename(path), cutlist)
			return CutList(self, cutlist_meta_dict={'id':hash(repr(cutlist))}, cutlist_dict=cutlist)
		else:
			return None
		
	def GetCutList(self, cl_id):
		raise NotImplementedError("Method has not to be called")

	#
	# getView
	#
	def getView(prov, path):
		filename = os.path.basename(path)
		
		class View:
			def __init__(self):
				self.cutlists = prov.getCutlists(filename)
				print "%d Cutlist(s) wurde(n) schon von Ihnen für diese Datei erstellt" % len(self.cutlists)

				for i, cutlist in enumerate(self.cutlists):
					print "[%2d] Cutlist: %s" % (i+1,cutlist[0])
				print "[ n] neue Cutlist erstellen"

			def getCutlist(self, inp, **kwargs):
				if inp.strip() == 'n':
					cutlist = prov.createCutlist(path)
					if cutlist:
						self.cutlists.append( ('neu erstellt', cutlist) )
						print "[%2d] Cutlist: %s" % (len(self.cutlists),self.cutlists[-1][0])
					return cutlist
				else:
					try:
						i = int(inp)-1
						if 0 <= i < len(self.cutlists):
							return self.cutlists[i][1]
						else:
							print "Illegaler Index."
							return None
					except:
						print "Illegale Eingabe."
						return None
		return View()

	#
	# upload cutlist
	#
	def PostProcessCutList( self, cl_id, cutlist ):
		if not self.cutoptions.cutlistathash:
			print "Kein Cutlist.at-Benutzerhash angegeben, daher kann die Cutlist nicht hochgeladen werden."
			return
		
		s = raw_input("Cutlist hochladen [J/n]: ").strip()
		if 'n' in s.lower():
			return

		cutlisttxt = cutlist.GenerateCompleteCutList()
		if cutlisttxt:
			CutListAT.UploadCutList(self.cutoptions.cutlistathash, cutlisttxt)
		else:
			print
			print "Vorgang abgebrochen, die Cutlist wird nicht hochgeladen!"
			print

###
# CutListFileProvider
###
class CutListFileProvider:
	"""
	allows local cutlists
	"""
	def __init__(self, cutoptions):
		self.cutoptions = cutoptions
		self.desc = "Cutlists von der Festplatte benutzen."
	
	def GetCutList(self, cl_id):
		Debug(2, "CutListFileProvider::GetCutList: %s" % cl_id)
		return open(cl_id).read()

	#
	# getView
	#
	def getView(prov, path):
		class View:
			def __init__(self):
				print "[  ] Dateipfad eingeben."
			
			def getCutlist(self, inp, **kwargs):
				if os.path.isfile(inp):
					return CutList(prov,cutlist_meta_dict={'id':inp})
				else:
					print "'%s' ist keine gültige Datei." % inp
					return None
		return View()

	#
	# noop
	#
	def PostProcessCutList( self, cl_id, cutlist ):
		pass
###
# CutListGenerator
###
class CutListGenerator:
	"""
	generates cutlists
	"""
	def __init__(self, cutlistprov):
		self.cutlistprov = cutlistprov
	
	def makeCutList(self, filename):
		self.filename = filename
		self.basename = os.path.basename(filename)
		self.tmpname = "%s_own_project.js" % random.getrandbits(32)
		self.tmppath = os.path.join(self.cutlistprov.cutoptions.tempdir, self.tmpname)
		self.writePreAvidemuxProject()
		
		#
		# start avidemux
		#

		print "%s Starte Avidemux. Das Projekt muss manuell gespeichert werden und Avidemux beendet. %s" % (C_RED, C_CLEAR)
		cmdoptions = ["--force-smart", "--run", self.tmppath]
		if self.cutlistprov.cutoptions.aviDemux_saveWorkbench:
			cmdoptions += ["--save-workbench", self.tmppath]
		out, err = Run(self.cutlistprov.cutoptions.cmd_AviDemux_Gui, cmdoptions)
		
		#
		# post processing
		#
		try:
			project = open(self.tmppath, 'r').read()
		except:
			print "Keine Datei gespeichert!"
			return None
		if not "app.addSegment" in project:
			print "Keine Schnitte angegeben!"
			return None

		if "app.video.fps1000" in project:
			grapFPS = project.split("app.video.fps1000")[1].split('=')[1].split(';')[0].strip()
		else:
			grapFPS = project.split("app.video.setFps1000")[1].split('(')[1].split(')')[0].strip()
		self.FPS = float(grapFPS)*0.001
		
		#
		# creating cutlist data
		#
		cutlist = {}
		
		cuts = []
		segments = project.split("app.addSegment(")[1:]
		for segment in segments:
			start    = int( segment.split(',')[1] )
			duration = int( segment.split(',')[2].split(')')[0] )
			cuts.append( (start, duration) )
		
		cutlist["frames"] = cuts
		cutlist["fps"] = self.FPS
		cutlist["file"] = self.basename
		cutlist["size"] = os.path.getsize(self.filename)

		return cutlist
	
	def writePreAvidemuxProject(self):
		pstr = '//AD\n'\
			+ 'var app = new Avidemux();\n'\
			+ 'app.load("%s");\n' % self.filename
		open(self.tmppath, "a").write(pstr)
	


		

###
# CutOptions Class
###
class CutOptions:
	"""
	defines options used throughout the program
	"""
	def __init__(self, configfile = None, options = None):
		# init values
		self.tempdir = tempfile.mkdtemp(prefix = "multicut_evolution")
		self.cutdirformat = os.getcwd()
		self.uncutdir= os.getcwd()
		self.cachedir= os.path.expanduser("~/.cache/multicut_evolution/")
		self.author  = pwd.getpwuid(os.getuid())[0]
		self.only_internet = bool(options.only_internet) if options else False
		self.no_internet = bool(options.no_internet) if options else False
		self.no_comments = bool(options.no_comments) if options else False
		self.no_suggestions = bool(options.no_suggestions) if options else False
		self.cutlistathash = ""
		self.cutlistatall = False
		self.nfo = False
		
		self.cmd_VirtualDub = None
		self.cmd_AviDemux_Gui = "avidemux2_qt4"
		self.cmd_Ac3fix = None
		self.aviDemux_saveWorkbench = True
		self.do_rate = True
		self.convertmkv = False
		self.convertonlywac3tomkv = False
		self.delavi = False
		self.useac3 = True
		
		self.cutnameformat = "{base}-cut{rating}.{ext}"
		self.uncutnameformat = "{full}"

		self.time_before_cut = 10
		self.time_after_cut  = 5
		
		# parse
		if configfile:
			print "Parse Konfigurationsdatei: %s" % configfile
			self.ParseConfig(configfile)
		
		# enforce existence
		for d in [self.uncutdir,self.cachedir]:
			if not os.path.exists(d):
				Debug(4, "init: create directory: %s" % d)
				os.makedirs(d)
				
		# find avidemux
		for avidemux in avidemux_cmds:
			try:
				out = Run(avidemux, ["--quit"])[0]
				self.cmd_AviDemux = avidemux
				if "Avidemux v2.5" in out:
					self.cmd_AviDemux_version = "2.5"
					break
				elif "Avidemux v2.4" in out:
					self.cmd_AviDemux_version = "2.4"
					break
				else:
					continue # do not use
			except OSError:
				pass # not found
		else:
			raise RuntimeError("avidemux not found")
		
		print "Benutze als temp-Verzeichnis: %s" % self.tempdir
		print "Benutze als cut-Verzeichnisformat: %s" % self.cutdirformat
		print "Benutze als uncut-Verzeichnis: %s" % self.uncutdir
		print "Benutze als cache-Verzeichnis: %s" % self.cachedir
		print "Benutze als cutnameformat: %s" % self.cutnameformat
		print "Benutze als uncutnameformat: %s" % self.uncutnameformat
		print "Benutze als AviDemux: %s (v:%s)" % (self.cmd_AviDemux, self.cmd_AviDemux_version)
		print "Benutze als VirtualDub: %s" % self.cmd_VirtualDub

		self.cutlistprovider = {}
		self.defaultproviderlist = []
		if not self.no_internet:
			self.cutlistprovider['internet'] = CutListAT(self)
			self.defaultproviderlist.append('internet')
		if not self.only_internet:
			self.cutlistprovider['own']  = CutListOwnProvider(self)
			self.cutlistprovider['file'] = CutListFileProvider(self)
			self.defaultproviderlist.append('own')

		self.DefaultProjectClass = AviDemuxProjectClass
		self.RegisteredProjectClasses = {}
		if self.cmd_VirtualDub:
			self.RegisteredProjectClasses[".mpg.HQ.avi"] = VDProjectClass
			self.RegisteredProjectClasses[".mpg.HD.avi"] = VDProjectClass
		
		
	def ParseConfig(self, config):
		config = os.path.expanduser(config)
		Debug(1, "CutOptions::ParseConfig: open config '%s'" % config)
		try:
			for line in open(config):
				if not line.strip():
					continue
				try:
					cmd, opt = line.split("=",1)
					cmd, opt = cmd.strip(), opt.strip()
					Debug(2, "CutOptions::ParseConfig: config read:'%s' = '%s'" % (cmd,opt))
					if cmd == "cutdir":
						self.cutdirformat = opt
					elif cmd == "uncutdir":
						self.uncutdir= os.path.expanduser(opt)
					elif cmd == "virtualdub":
						self.cmd_VirtualDub = os.path.expanduser(opt)
					elif cmd == 'avidemux_gui':
						self.cmd_AviDemux_Gui = os.path.expanduser(opt)
					elif cmd == 'ac3fix':
						self.cmd_Ac3fix = os.path.expanduser(opt)
					elif cmd == "cachedir":
						self.cachedir= os.path.expanduser(opt)

					elif cmd == "cutname":
						self.cutnameformat = opt
					elif cmd == "uncutname":
						self.uncutnameformat = opt
					elif cmd == "author":
						self.author = opt
					elif cmd == "cutlistathash":
						self.cutlistathash = opt

					elif cmd == "vorlauf":
						self.time_before_cut = int(opt)
					elif cmd == "nachlauf":
						self.time_after_cut  = int(opt)

					elif cmd == "review":
						self.do_rate = not (opt.lower()=='false' or opt=='0')
					elif cmd == "cutlistatall":
						self.cutlistatall = (opt.lower()=='true' or opt=='1')
					elif cmd == 'avidemux_saveworkbench':
						self.aviDemux_saveWorkbench = not (opt.lower()=='false' or opt=='0')
					elif cmd == 'comments':
						self.no_comments = (opt.lower()=='false' or opt=='0')
					elif cmd == 'suggestions':
						self.no_suggestions = (opt.lower()=='false' or opt=='0')
					elif cmd == 'useac3':
						self.useac3 = not (opt.lower()=='false' or opt=='0')
					elif cmd == 'convertmkv':
						self.convertmkv = not (opt.lower()=='false' or opt=='0')
					elif cmd == 'convertonlywac3tomkv':
						self.convertonlywac3tomkv = not (opt.lower()=='false' or opt=='0')
					elif cmd == 'delavi':
						self.delavi = not (opt.lower()=='false' or opt=='0')
					elif cmd == 'nfo':
						self.nfo = not (opt.lower()=='false' or opt=='0')


				except StandardError, e:
					print "ConfigParse: Could not parse '%s' due to:" % line
					print e
		except:
			pass
	
	def FormatString(self, name, data):
		if name == "cutname" or name == "uncutname" or name == "cutdir":
			cutlist, filename = data
			format = {}
			# cutlist relevant
			format["rating"] = str(int(100*float(cutlist["rating"])+0.5)) if "rating" in cutlist and cutlist["rating"] else ''
			format["metarating"] = str(int(100*float(cutlist["metarating"])+0.5))
			#filename relevant
			format["full"] = filename
			format["base"], format["shortext"] = filename.split(".mpg.")
			format["ext"] = 'mpg.%s' % format["shortext"]
			if name == "cutname":
				return self.cutnameformat.format(**format)
			elif name == "uncutname":
				return self.uncutnameformat.format(**format)
			elif name == "cutdir":
				return self.cutdirformat.format(**format)
			
		raise ValueError("'%s' is not valid" % name)


class DeletedException(StandardError):
	pass

###
# CutFile Class
###
class CutFile:
	"""
	select cutlist and cut file, optional select imdb tt
	"""
	def __init__(self, path, cutoptions):
		self.path = { 'avi': os.path.realpath(path) }
		self.cutoptions = cutoptions
		
		self.filename = os.path.basename(path)
		self.opener = urllib2.build_opener()
		self.opener.addheaders = [('User-agent', 'Mozilla/5.0')]

	def ChooseCutList(self):
		print 
		print "	%s %s %s" % (C_RED, self.filename, C_CLEAR)
		print 

		self.currentprov = None
		self.cutlist = None
		
		while not self.cutlist:
			if not self.currentprov:
				for prov in self.cutoptions.defaultproviderlist:
					try:
						print "Wähle automatisch den Provider '%s'" % prov
						self.currentprov = self.cutoptions.cutlistprovider[prov].getView(self.path['avi'])
						break
					except LookupError:
						print "Fehlgeschlagen, nehme nächsten..."
						print #newline
				else:
					print "Es wurden keine weiteren Provider gefunden."
					print "Datei wird nicht geschnitten, da keine Cutlist gefunden wurde."
					return False
					
			inp = raw_input("Auswahl/Test: ").strip()
			print
			
			if inp.lower() == "delete" or unicode(inp.lower(),'utf8') == u"löschen":
				s = raw_input("Soll die Datei gelöscht werden? [j/N] ").strip()
				if s.lower() == 'j':
					print "%s Lösche %s %s" % (C_RED, self.path['avi'], C_CLEAR)
					try:
						os.remove(self.path['avi'])
						raise DeletedException()
					except OSError:
						print "Datei konnte nicht gelöscht werden."
						return False
				print
				continue

			
			if not inp:
				print "Datei wird nicht geschnitten"
				return False
			
			specials = []
			
			# consume input string
			while inp.strip():
				inp = inp.lstrip()
				
				for prov in self.cutoptions.cutlistprovider.keys():
					if inp.startswith(prov.lower()):
						inp = inp[len(prov):]
						
						print "Wechsel zu Provider '%s'" % prov
						self.currentprov = self.cutoptions.cutlistprovider[prov].getView(self.path['avi'])
						break
				else:
					for flag in ['test', "cat"]:
						if inp.lower().startswith(flag):
							specials.append(flag)
							inp = inp[len(flag):]
							break
					else:
						data, _, inp = inp.partition(' ')
						self.cutlist = self.currentprov.getCutlist(data, currentcutlist = self.cutlist)

			if specials:
				if self.cutlist:
					if 'test' in specials:
						self.cutlist.ShowCuts(self.path['avi'], is_filecut = False, tempdir = self.cutoptions.tempdir)
					if 'cat' in specials:
						try:
							cutlist = self.cutlist.GetRawCutList()
						except:
							cutlist = self.cutlist.GenerateRawCutList()
						print "Cutlist:"
						for line in cutlist.strip().split('\n'):
							print ">", line
						print
					self.cutlist = None
				else:
					print "Keine Cutlist angegeben!"
		
		# set names
		self.cutname = self.cutoptions.FormatString("cutname", (self.cutlist, self.filename))
		self.tmpname = "$$$$-" + self.cutname 
		self.uncutname = self.cutoptions.FormatString("uncutname", (self.cutlist, self.filename))
		# set and create cutdir directory
		self.cutdir = os.path.expanduser(self.cutoptions.FormatString("cutdir", (self.cutlist, self.filename)))
		if not os.path.exists(self.cutdir):
			Debug(4, "Cutfile.ChooseCutList: create directory: %s" % self.cutdir)
			os.makedirs(self.cutdir)

		if not self.cutoptions.no_suggestions:
			cutlist_dict = self.cutlist.GetCutListDict()
			suggested = cutlist_dict['suggested'].strip() if 'suggested' in cutlist_dict else None
			if suggested:
				if not suggested.endswith('.avi'):
					suggested += '.avi'
				print
				print "Die Cutlist enthält einen Dateinamenvorschlag:"
				print "    [c] %s" %suggested
				print "    [g] %s (generischer Vorschlag)" % self.cutname
				inp = raw_input("Wollen Sie den [g]enerischen Vorschlag (Standard) oder den [c]utlist-Vorschlag benutzen? ").strip()
				if inp.lower() == 'c':
					self.cutname = suggested
					print "Benutze '%s'" % self.cutname
		
		return True


	def Cut(self):
		self.cutpath = {'avi': os.path.join(self.cutdir, self.cutname) }
		self.tmppath = {'avi': os.path.join(self.cutdir, self.tmpname) }
		self.uncutpath = {'avi': os.path.join(self.cutoptions.uncutdir, self.uncutname) }

		print "%s Schneide %s %s" % (C_RED, self.filename, C_CLEAR)
		print "Ausgabename: %s" % self.cutname
		
		
		for extension, registeredclass in self.cutoptions.RegisteredProjectClasses.items():
			if extension in self.filename:
				projectclass = registeredclass
				break
		else:
			projectclass = self.cutoptions.DefaultProjectClass
		
		project = projectclass(self, self.cutlist, self.cutoptions)
		
		print "Schneide mit %s" % project.Name()
		
		start = time.time()
		project.Run() # run
		end = time.time()
		print "Fertig, benötigte Zeit: %ds" % int(end-start+0.5)
			
		if os.path.isfile(self.tmppath['avi']):
			for entry in self.path:
				shutil.move(self.path[entry], self.uncutpath[entry])
			for entry in self.tmppath:
				shutil.move(self.tmppath[entry], self.cutpath[entry])
			return True
		else:
			print "Schneiden war nicht erfolgreich"
			return False

	def ConvertMkv(self):
		#if os.path.splitext(self.cutpath)[1].lower() == '.ac3':
		#	return
		self.cutpath['mkv'] = os.path.splitext(self.cutpath['avi'])[0] + '.mkv'
		#ac3path = os.path.splitext(self.cutpath)[0] + '.ac3'
		print "\n%s Konvertiere %s %s" % (C_RED, self.cutpath['avi'], C_CLEAR)
		start = time.time()
		mkvcmd = ['mkvmerge', '-o', self.cutpath['mkv'], '--compression', '-1:none', self.cutpath['avi']]
		if 'ac3' in self.cutpath:
			mkvcmd += [self.cutpath['ac3']]
		subprocess.Popen(mkvcmd).wait()
		end = time.time()
		print "Konvertieren abgeschlossen, benötigte Zeit: %ds" % int(end-start+.5)

	def SplitIMDB(self,html):
		parts = re.split('\d+\.</td><td valign="top">', html)
		choices = []
		for p in parts:
			if not 'title/tt' in p or 'Displaying' in p:
				continue
			choices.append([])
			choices[-1].append(p.split('/title/')[1].split('/')[0])
			choices[-1].append(p.split(';">')[1].split('</a>')[0].strip())
			choices[-1].append(p.split('</a>')[1].split('<p')[0].split('</td')[0].strip())
		return choices
	
	def WriteNFO(self):
		print "%s Finde IMDB für %s %s" % (C_RED, self.filename, C_CLEAR)
		nice = re.match('(.*)_\d\d.\d\d.\d\d_\d\d-\d\d', self.filename).group(1)
		replaces = { '_': ' ', 'ae': 'ä', 'oe': 'ö', 'ue': 'ü', 'Ae': 'Ä', 'Oe': 'Ö', 'Ue': 'Ü'}
		for r in replaces:
			nice = nice.replace(r, replaces[r])
		retrieve = self.opener.open('http://www.imdb.com/find?q=%s&s=all' % urllib.quote(nice))
		rawpage = unicode(retrieve.read(), 'utf-8')
		accept = False
		if 'title/tt' in retrieve.geturl():
			r = rawpage.split('<h1 class="header" itemprop="name">')[1].split('</h1>')[0].split('<span class="nobr">')
			name = r[0].strip()
			year = r[1].split('href="')[1].split('">')[1].split('</a>')[0]
			tt = retrieve.geturl().split('title/')[1].split('/')[0]
			print "Exakten Treffer gefunden: %s - %s (%s)" % (tt, name, year)
			if raw_input("Akzeptieren (J/n): ").lower() not in ['n']:
				accept = True
		else:
			exact = None
			partial = None
			if '<p><b>Titles (Exact Matches)</b>' in rawpage:
				exact = self.SplitIMDB(rawpage.split('<p><b>Titles (Exact Matches)</b>')[1].split('</table> </p>')[0])
			if '<p><b>Titles (Partial Matches)</b>' in rawpage:
				partial = self.SplitIMDB(rawpage.split('<p><b>Titles (Partial Matches)</b>')[1].split('</table> </p>')[0])
			if exact:
				print "Mehrere exakte Treffer gefunden"
				for i,e in enumerate(exact):
					print "[ %2d] %s - %s %s" % (i+1, e[0], e[1], e[2])
				print "[ n] oder leere Eingabe: kein passender Treffer"
				num = raw_input("Auswahl(1,1-3,1-2-9): ").strip()
				try:
					num = int(num)
					accept = True
					tt = exact[num-1][0]
				except:
					pass
			if partial and not accept:
				print "Mehrere partielle Treffer gefunden"
				for i,e in enumerate(partial[:10] if len(partial) > 10 else partial):
					print "[ %2d] %s - %s %s" % (i+1, e[0], e[1], e[2])
				print "[ n] oder leere Eingabe: kein passender Treffer"
				num = raw_input("Auswahl(1,1-3,1-2-9): ").strip()
				try:
					num = int(num)
					accept = True
					tt = partial[num-1][0]
				except:
					pass
		if not accept:
			print "Bitte geben sie die IMDB tt von Hand an!"
			t = raw_input("IMDB tt: ").strip()
			if re.match('tt\d\d\d\d\d\d\d', t):
				tt = t
				accept = True
		if accept:
			with open(os.path.splitext(self.cutpath['avi'])[0] + '.nfo', 'w') as f:
				f.write('http://www.imdb.com/title/%s\n' % tt)

	def ValidateCut(self):		
		print "%s Prüfe %s %s" % (C_RED, self.filename, C_CLEAR)
		self.cutlist.ShowCuts(self.cutpath['avi'], is_filecut = True, tempdir = self.cutoptions.tempdir)
		self.cutlist.PostProcessCutList()
		
		print
		s = raw_input("Soll die geschnitte Datei angenommen werden? [J/n]: ").strip()
		if 'n' in s.lower():
			s = raw_input("Soll die geschnitte Datei wirklich gelöscht und die Originaldatei wiederhergestellt werden? [J/n] ").strip()
			if not 'n' in s.lower():
				for entry in self.cutpath:
					print "%s Lösche %s %s" % (C_RED, self.cutpath[entry], C_CLEAR)
					try:	os.remove(self.cutpath[entry])
					except: pass # doesn't matter
					shutil.move(self.uncutpath[entry], self.path[entry])
				return False
		return True
					
	def GetQuality(self):
		if ".mpg.HQ" in self.filename:
			return '+'
		elif ".mpg.HD" in self.filename:
			return 'H+'
		else:
			raise ValueError("Could not determine the quality of the file '%s'" % self.filename)

	def GetAspect(self):
		out = Run("mplayer",  ["-vo", "null", "-nosound", "-frames", "1", self.path['avi']])[0]
		if "Movie-Aspect is 1.33:1" in out or "Film-Aspekt ist 1.33:1" in out:
			return "4:3"
		if "Movie-Aspect is 0.56:1" in out or "Film-Aspekt ist 0.56:1" in out:
			return "16:9"
		if "Movie-Aspect is 1.78:1" in out or "Film-Aspekt ist 1.78:1" in out:
			return "16:9"
		return "4:3"
	
	def GetSampleAspect(self):
		""" Gets the aspect ratio of a movie using mplayer.
		Returns without error:
		aspect_ratio, None
		with error:
		None, error_message 
		from https://github.com/monarc99/otr-verwaltung/blob/23afd48461a78bc2f090685c18f0c1a36b59f043/otrverwaltung/actions/decodeorcut.py#L461"""
		out = Run("mplayer", ["-msglevel", "all=6", "-vo", "null", "-frames", "1", "-nosound", self.path['avi']])[0]
		
		infos_match = re.compile(r"VO Config \((\d{1,})x(\d{1,})->(\d{1,})x(\d{1,})")

		for line in out.split('\n'):
			m = re.search(infos_match,line)
			if m:
				sar = Fraction( int(m.group(3)), int(m.group(1)) )
				if sar.numerator == 427 and sar.denominator == 360:
					return "32:27"
				else:
					return str(sar.numerator) + ":" + str(sar.denominator)
			else:
				pass
		print "Sample Aspect Ratio konnte nicht bestimmt werden!"
		r = raw_input("Sample Aspect Ratio eingeben (Format: num:denom, Enter skips): ").strip()
		if ':' in r:
			return r
		raise Exception("Sample Aspect Ratio konnte nicht bestimmt werden.")

###
# AviDemuxProjectClass
###
class AviDemuxProjectClass:
	"""
	avidemux project wrapper
	"""
	def __init__(self, cutfile, cutlist, cutoptions):
		self.cutfile = cutfile
		self.cutlist = cutlist
		self.cutoptions = cutoptions

		self.filename = os.path.join(self.cutoptions.tempdir, "%d_project.js" % random.getrandbits(32))

		self.Start(self.cutfile.path['avi'])
		
		StartInFrames, DurationInFrames = self.cutlist.TimesInFrames()
		for start, duration in zip(StartInFrames, DurationInFrames):
			self.Append("app.addSegment(0,%d,%d);" % (start, duration))
		
		self.End(self.cutfile.tmppath['avi'], self.cutoptions.cmd_AviDemux_version, self.cutlist.GetFPS())

	def Name(self):
		return "Avidemux"
	
	def Write(self, text, mode = "a"):
		open(self.filename, mode).write(text)
	
	def Start(self,path):
		text = 	'//AD\n' \
			 +	'var app = new Avidemux();\n' \
			 +	'//** Video **\n' \
			 +	'// 01 videos source\n' \
			 +	'app.load("%s");\n' % path \
			 + 	'\n' \
			 +	'// 02 segments\n' \
			 +	'app.clearSegments();\n'
		self.Write(text,"w")
	
	def Append(self, append):
		self.Write(append + "\n")
	
	def End(self,tmppath,version,fps):
		if version == "2.5":
			text = 	'app.video.setPostProc(3,3,0);\n' \
				+	'app.video.fps1000=%d;\n' % (fps*1000) \
				+	'app.video.codec("Copy","CQ=4","0 ");\n' \
				+	'app.audio.reset();\n' \
				+ 	'app.audio.codec("copy",128,0,"");\n' \
				+	'app.audio.normalizeMode=0;\n' \
				+	'app.audio.normalizeValue=0;\n' \
				+	'app.audio.delay=0;\n' \
				+	'app.audio.mixer="NONE";\n' \
				+	'app.audio.scanVBR="";\n' \
				+	'app.setContainier="AVI";\n' \
				+ 	'setSuccess(app.save("%s"));\n' % tmppath
		else:
			text = 	'app.video.setPostProc(3,3,0);\n' \
				+	'app.video.setFps1000(%d);\n' % (fps*1000) \
				+	'app.video.codec("Copy","CQ=4","0 ");\n' \
				+	'app.audio.reset();\n' \
				+ 	'app.audio.codec("copy",128,0,"");\n' \
				+	'app.audio.normalizeMode=0;\n' \
				+	'app.audio.normalizeValue=0;\n' \
				+	'app.audio.delay=0;\n' \
				+	'app.audio.mixer("NONE");\n' \
				+	'app.audio.scanVBR();\n' \
				+	'app.setContainer("AVI");\n' \
				+ 	'setSuccess(app.save("%s"));\n' % tmppath
		self.Write(text,"a")
	
	def Run(self):
		Debug(1, "starting avidemux")
		return Run(self.cutoptions.cmd_AviDemux, ["--force-smart", "--run", self.filename, "--quit"])

###
# VDProjectClass
###
class VDProjectClass:
	"""
	VD project wrapper
	"""
	def __init__(self, cutfile, cutlist, cutoptions):
		self.cutfile = cutfile
		self.cutlist = cutlist
		self.cutoptions = cutoptions

		self.projectname = "%d_project.syl" % random.getrandbits(32)
		self.filename = os.path.join(self.cutoptions.tempdir, self.projectname)
			
		self.Start(self.cutfile.path['avi'])
			
		self.SetAspectRatio(self.cutfile.GetAspect(),self.cutfile.GetQuality(),self.cutfile)
			
		self.Append("VirtualDub.subset.Clear();")
		StartInFrames, DurationInFrames = self.cutlist.TimesInFrames()
		for start, duration in zip(StartInFrames, DurationInFrames):
			self.Append("VirtualDub.subset.AddRange(%d,%d);" % (start, duration))

		self.End(self.cutfile.tmppath['avi'])
		self.prepareAC3()

	def prepareAC3(self):
		self.ffmpegcmd = None
		if self.cutoptions.useac3:
			ac3 = self.testAC3()
			if ac3:
				Starts, Durations = self.cutlist.TimesInSeconds()
				if len(Starts)>1:
					print "More than 1 cut for ac3! Not yet implementet!"
					return
				self.ffmpegcmd = ['ffmpeg', '-y', '-i', self.cutfile.path['ac3'], '-ss', '%f' % Starts[0],
					'-t', '%f' % Durations[0], '-acodec', 'copy', self.cutfile.tmppath['ac3']]

	def testAC3(self):
		Debug(1, "Testing for AC3")
		if self.cutfile.GetQuality() == 'H+':
			ac3source = os.path.splitext(self.cutfile.path['avi'])[0] + '.ac3'
			if os.path.exists(ac3source):
				Debug(2, "AC3 found")
				if self.cutoptions.cmd_Ac3fix:
					Debug(2, "Testing AC3")
					ac3tmptarget = ac3source + '.fix.ac3'
					ac3fixcmd = ['wine', self.cutoptions.cmd_Ac3fix, ac3source, ac3tmptarget]
					out,err=subprocess.Popen(ac3fixcmd, stdout = subprocess.PIPE, stderr=subprocess.PIPE).communicate()
					try: os.remove(ac3tmptarget)
					except: pass
					if "Found bad frames" in out:
						print "AC3-File beschädigt. Benutztung würde vermutlich zu Asyncronität führen. Fahre ohne AC3 fort."
						return False
					Debug(2, "AC3 ok")
					ac3target =  os.path.splitext(self.cutfile.tmppath['avi'])[0] + '.ac3'
					ac3uncut =  os.path.splitext(self.cutfile.uncutpath['avi'])[0] + '.ac3'
					ac3cut =  os.path.splitext(self.cutfile.cutpath['avi'])[0] + '.ac3'
					self.cutfile.path['ac3'] = ac3source
					self.cutfile.tmppath['ac3'] = ac3target
					self.cutfile.uncutpath['ac3'] = ac3uncut
					self.cutfile.cutpath['ac3'] = ac3cut
					return True
		return False

	def Name(self):
		return "VirtualDub"
		
	def Write(self, text, mode = "a"):
		open(self.filename, mode).write(text)

	def Start(self, path):
		text = 	'VirtualDub.Open("%s",0,0);\n' % path \
			 +	'VirtualDub.audio.SetMode(0);\n' \
			 +	'VirtualDub.video.SetMode(1);\n' \
			 +	'VirtualDub.video.SetSmartRendering(1);\n' \
#			 +	'VirtualDub.video.SetCompression(0x53444646,0,10000,0);\n'
		self.Write(text, "w")
		
	def Append(self, append):
		self.Write(append + '\n')
	
	def SetAspectRatio(self, ratio, quality, cutfile):
		# Hier muss man aufpassen und nach verschiedenen Formaten differenzieren
		# source:
		# http://github.com/elbersb/otr-verwaltung/blob/master/otrverwaltung/codec.py#L14
		# aktuellere source: http://www.otrforum.com/showthread.php?t=53400&p=324062&viewfull=1#post324062
		# aktuellere source: https://github.com/monarc99/otr-verwaltung/blob/23afd48461a78bc2f090685c18f0c1a36b59f043/otrverwaltung/actions/decodeorcut.py#L692
		sample_aspect = self.cutfile.GetSampleAspect()
		if quality == '+' :
			Debug(2, '16:9 HQ')
			Debug(4,'Blob: VirtualDub.video.SetCompData(2994,"ADLICwAAAADRC1lWMTK6C5CyCAAnDf////8ZDRA...')
			self.Append('VirtualDub.video.SetCompression(0x34363278,0,10000,0);')
			self.Append('VirtualDub.video.SetCompData('+get_comp_data_x264vfw_dynamic(sample_aspect,h264_settings['x264vfw_hq_string'])+');')
		elif quality == 'H+':
			Debug(2, '16:9 HD')
			Debug(4,'Blob: VirtualDub.video.SetCompData(2974,"ADLICwAAAADRC1lWMTK6C5CyCAAnD...')
			self.Append('VirtualDub.video.SetCompression(0x34363278,0,10000,0);')
			self.Append('VirtualDub.video.SetCompData('+get_comp_data_x264vfw_dynamic(sample_aspect,h264_settings['x264vfw_hd_string'])+');')
		else:
			raise ValueError("Could not determine the quality of the video. (%s)" % quality)

	def End(self, cutpath):
		text =	'VirtualDub.SaveAVI("%s");\n' % cutpath \
			 +	'VirtualDub.Close();\n'
		self.Write(text)

	def Run(self):
		os.chdir(self.cutoptions.tempdir)

		Debug(1, "starting vd")
		#vdub_cmd = '/home/matthias/Documents/Programmieren/Python/multicut_evolution/otr-verwaltung/data/media/intern-VirtualDub/vdub.exe'
		winedir = os.path.dirname(self.cutoptions.cmd_VirtualDub)
		#sub = subprocess.Popen(args = 'WINEPREFIX=' + winedir + '/wine' + " wineconsole  %s /x /s %s" % (vdub_cmd,self.projectname),
		#									shell = True, stderr = subprocess.PIPE, stdout = subprocess.PIPE)
		sub = subprocess.Popen(args = 'WINEPREFIX=' + winedir + '/wine' + " wine  %s /x /s %s" % (self.cutoptions.cmd_VirtualDub,self.projectname),
											shell = True, stderr = subprocess.PIPE, stdout = subprocess.PIPE)
		
		# Make read calls non blocking
		# from https://stackoverflow.com/questions/8980050/persistent-python-subprocess
		fcntl.fcntl(sub.stderr.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
		errtext = ''
		while True:
			if sub.poll() != None:
				break
			try:
				output = subprocess.check_output(['wmctrl', '-l'], stderr=subprocess.PIPE)
				windows = output.split('\n')
				windows = [w for w in windows if 'virtualdub' in w.lower()]
				if windows:
					parts = windows[0].split()
					parts = [p for p in parts if '%' in p]
					print '\rProgress', parts[0],
					sys.stdout.flush()
			except Exception as e:
				#print e
				pass
			try:
				adderrtxt = sub.stderr.read()
			except IOError:
				continue
			if adderrtxt == '\n':
				Debug(4, errtext.rpartition('\n')[-1])
			errtext += adderrtxt
			if 'fixme:avifile:AVIFileExit' in errtext:
				sub.send_signal(9) # python >=2.6(?)
				break
			time.sleep(0.3)
		print
		if self.ffmpegcmd:
			Debug(1, "starting ffmpeg with %r" % self.ffmpegcmd)
			subprocess.Popen(self.ffmpegcmd, stdout = subprocess.PIPE, stderr = subprocess.PIPE).wait()

###
# main function
###
def main():
	parser = optparse.OptionParser(add_help_option=False)
	def error(msg):
		print C_RED + str(msg) + C_CLEAR # will print something like "option -a not recognized"
		print
		print prog_help
		sys.exit(1)
	parser.error = error
	parser.add_option("-h", "--help", action="store_true", default=False)
	parser.add_option("--inst-help", action="store_true", default=False)
	parser.add_option("--config-help", action="store_true", default=False)
	
	parser.add_option("-n", "--nocheck", action="store_true", default=False)
	parser.add_option("-i", "--only-internet", action="store_true", default=False)
	parser.add_option("-o","--no-internet","--offline", dest="no_internet", action="store_true", default=False)
	parser.add_option("-c", "--no-comments", action="store_true", default=False)
	parser.add_option("-s", "--no-suggestions", action="store_true", default=False)

	parser.add_option("--config",dest="configfile",default="~/.multicut_evolution.conf")

	parser.add_option("--verbosity",type="int",default=0)
	parser.add_option("-v",action="count",dest="verbosity")

	options, args = parser.parse_args()

	global VERBOSITY_LEVEL
	VERBOSITY_LEVEL = options.verbosity

	if options.help:
		print prog_help
		sys.exit()
	if options.config_help:
		print prog_config_help
		sys.exit()
	if options.inst_help:
		print prog_inst_help
		sys.exit()


	o = CutOptions(options.configfile, options)


	###
	# choose cutlists
	###
	avis = []
	for avi in args:
		if not avi.endswith(".avi"):
			print "Non-Avi Datei ausgelassen: %s" % avi
			continue
		else:
			avis.append(avi)
	
	avis.sort()
	avis2Choose = avis
	cutfiles = {}
	
	print
	print
	print "%s Cutlists auswählen für insgesamt %d Datei(en): %s" %(C_RED_UNDERLINE, len(avis), C_CLEAR)
	print
	print "Verfügbare Provider:"
	if len(o.cutlistprovider) == 0:
		print "%sEs wurde kein Provider gefunden, überprüfen Sie ihre Parameter.%s" % (C_RED,C_CLEAR)
		sys.exit()
	for key, value in sorted(o.cutlistprovider.items(), key=lambda x:x[0]): #sort by name
		std = " [Standard]" if key == o.defaultproviderlist[0] else ""
		print "  %s - %s%s" % (key,value.desc,std)
	print
	print
	
	
	while avis2Choose:
		# choose
		print
		print
		print "%s Cutlists auswählen für %d Datei(en): %s" %(C_RED, len(avis2Choose), C_CLEAR)
		print
		
		for avi in avis2Choose[:]:
			try:
				c = CutFile(avi, o)
				if c.ChooseCutList():
					cutfiles[avi] = c
				else:
					if avi in cutfiles:
						del cutfiles[avi]
			except DeletedException:
				avis.remove(avi)
			except StandardError, e:
				print "Ein Fehler ist aufgetreten, die Datei wird nicht geschnitten: %s" % e
				Debug(1, traceback.format_exc())

		if not avis:
			print
			print "Keine Datei zum Schneiden gefunden."
			return
			

		print
		print
		print "%s Cutlists umwählen: %s" % (C_RED, C_CLEAR)
		print
		# confirm selection
		for i,avi in enumerate(avis):
			aviname = os.path.basename(avi)
			cut = 'x' if avi in cutfiles else ' '
			print "[%2d] %s %s" % (i+1,cut,aviname)
		print "[ a] alle neu wählen"
		print "[ n] oder leere Eingabe: nichts neu wählen und anfangen zu schneiden"
		
		avis2Choose = None
		while True:
			s = raw_input("Auswahl(1,1-3,1-2-9): ").strip()
			if not s or 'n' in s:
				break
			elif 'a' in s:
				avis2Choose = avis
				break
			else:
				try:
					iis = ParseIIRange(s)
					iis = sorted(list(set(iis)))
					iis = [i-1 for i in iis]
					if not (0 <= min(iis) and max(iis) < len(avis)):
						print "%sIhre Eingabe ist fehlerhaft, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
						continue
					avis2Choose = [avis[i] for i in iis]
					break
				except:
					print "%sEin Fehler ist aufgetreten, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
					continue

		
	cutfiles = cutfiles.values()
	cutfiles.sort(key=lambda x: x.filename)
	
	if not cutfiles:
		print
		print "Keine Datei zum Schneiden angegeben."
		return
	
	###
	# cut files
	###
	print
	print
	print
	print
	print "%s Schneide %d Datei(en): %s" %(C_RED_UNDERLINE, len(cutfiles), C_CLEAR)
	print

	checkfiles = []
	convertfiles = []
	errors = []
	
	for i,c in enumerate(cutfiles):
		print
		print "%d von %d" % (i+1, len(cutfiles))
		try:
			if c.Cut():
				checkfiles.append(c)
				convertfiles.append(c)
		except StandardError,e:
			print e
			print "Stacktrace:"
			traceback.print_exc()
			print "Life has to go on..."
			
			errors.append( (e,c) )
	
	try:
		if errors:
			print
			print
			print
			print "%s Es sind Fehler aufgetreten %s" % (C_RED, C_CLEAR)
			print
			for e,c in errors:
				print "Datei:", c.filename
				print "Fehler:", e
				#try:	print c.cutlist.GetCutList()
				#except Exception, e: print "Cutliste kann nicht angezeigt werden, wegen: '%s'" % e
				print
	except:
		print "Fehler während dem Anzeigen von Fehlern..."
	
	###
	# check files
	###
	if not options.nocheck:
		###
		# show files
		###
		print
		print
		
		checkfiles = [ [f,0] for f in checkfiles ]

		print
		print
		print "%s Schnitte überprüfbar von insgesamt %d Datei(en): %s" %(C_RED_UNDERLINE, len(checkfiles), C_CLEAR)
		print "Um die Cutlist, mit der einer dieser Film geschnitten wurde, hochzuladen, müssen Sie"
		print "zuerst die Schnitte überprüfen. Anschließend wird Ihnen diese Möglichkeit gegeben."
		print
		print
		
		while checkfiles:
			print
			print
			print "%s Schnitte überprüfen von %d Datei(en): %s" %(C_RED, len(checkfiles), C_CLEAR)
			print
			
			checkfiles.sort( key = lambda (_,n): n )
			filesNeedCheck = [ c_n for c_n in checkfiles if c_n[1] == 0 ]
			
			for i,(c,n) in enumerate(checkfiles):
				aviname = c.filename
				checked = "x" if n > 0 else " "
				print "[%2d] %s %s" % (i+1,checked,aviname)
			if filesNeedCheck:
				print "[ n] keine prüfen und beenden"
				print "[ f] alle überprüfen"
				print "[ a] oder leere Eingabe: alle noch nicht überprüften überprüfen"
			else:
				print "[ f] alle überprüfen"
				print "[ a] beenden"
				
			avis2Check = None
			while True:
				s = raw_input("Auswahl(1,1-3,1-2-9): ").strip()
				if not s or 'a' in s:
					avis2Check = filesNeedCheck if filesNeedCheck else None
					break
				elif 'f' in s:
					avis2Check = checkfiles
					break
				elif 'n' in s:
					avis2Check = None
					break
				else:
					try:
						iis = ParseIIRange(s)
						iis = sorted(list(set(iis)))
						iis = [i-1 for i in iis]
						if not (0 <= min(iis) and max(iis) < len(checkfiles)):
							print "%sIhre Eingabe ist fehlerhaft, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
							continue
						avis2Check = [checkfiles[i] for i in iis]
						break
					except:
						print "%sEin Fehler ist aufgetreten, versuchen Sie es erneut.%s" %(C_RED,C_CLEAR)
						continue
			
			if avis2Check == None:
				break

			for i,c_n in enumerate(avis2Check[:]):
				print
				print
				print "%d von %d" % (i+1, len(avis2Check))
				if c_n[0].ValidateCut(): # file was NOT deleted
					c_n[1] += 1
				else: # file was deleted
					checkfiles.remove(c_n)
	###
	# Write NFO File with IMDB ID
	# See http://wiki.xbmc.org/index.php?title=Nfo#Video_nfo_files_containing_an_URL
	###
	if o.nfo:
		print
		print
		print "%s IMDB Zuordnungen von %d Datei(en) durchführen: %s" %(C_RED, len(convertfiles), C_CLEAR)
		print
		for c in convertfiles:
			c.WriteNFO()
	
	###
	# MKV Conversion
	###
	if o.convertmkv:
		print
		print
		print "%s Konvertieren von %d Datei(en) ins MKV-Format: %s" %(C_RED, len(convertfiles), C_CLEAR)
		print

		for c in convertfiles:
			try:
				if o.convertonlywac3tomkv:
					if not 'ac3' in c.cutpath:
						continue
				c.ConvertMkv()
				if o.delavi:
					for entry in c.cutpath:
						if entry != 'mkv':
							print 'Lösche Datei %s' % c.cutpath[entry]
							os.remove(c.cutpath[entry])
			except StandardError,e:
				print e
				print "Stacktrace:"
				traceback.print_exc()
				print "There is still something to do..."


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		print
