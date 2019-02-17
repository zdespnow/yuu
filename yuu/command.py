import argparse
import shutil
import sys

from .downloader import *
from .parser import webparse, webparse_m3u8, parsem3u8
from .common import __version__

def main():
    parser = argparse.ArgumentParser(prog='yuu', description='A simple AbemaTV video downloader', epilog='Created by NoAiOne - Version {v}'.format(v=__version__))
    parser.add_argument('--proxies', '-p', required=False, default=None, dest='proxy', help='Use http(s)/socks5 proxies (please add `socks5://` if you use socks5)')
    parser.add_argument('--resolution', '-r', required=False, default='1080p', dest='res', choices=['180p', '240p', '360p', '480p', '720p', '1080p'], help='Resolution (Default: 1080p)')
    parser.add_argument('--output', '-o', required=False, default=None, dest='output', help='Output filename')
    parser.add_argument('--version', '-V', action='version', version='%(prog)s {v} - Created by NoAiOne'.format(v=__version__))
    parser.add_argument('--verbose', '-v', action='store_true', help="Enable verbose")
    parser.add_argument('input', help='AbemaTV url site or m3u8')

    args = parser.parse_args()
    print('[INFO] Starting yuu {ver}...'.format(ver=__version__))

    if args.proxy:
        print('[INFO] Testing proxy')
        sesi = requests.Session()
        sesi.proxies = {'http': args.proxy, 'https': args.proxy}
        # Someebody tell me how to do recursive test properly
        try:
            if args.verbose:
                print('[DEBUG] Testing http+https mode proxy')
            sesi.get('http://httpbin.org/get') # Some test website to check if proxy works or not
            pmode = "HTTP+HTTPS/SOCKS5"
        except:
            if args.verbose:
                print('[DEBUG] Failed')
            sesi = requests.Session()
            sesi.proxies = {'http': args.proxy}
            try:
                if args.verbose:
                    print('[DEBUG] Testing http mode proxy')
                sesi.get('http://httpbin.org/get') # This too but in https mode
                pmode = "HTTP/SOCKS5"
            except:
                if args.verbose:
                    print('[DEBUG] Failed')
                sesi = requests.Session()
                sesi.proxies = {'https': args.proxy} # Final test if it's failed then it will return error
                try:
                    if args.verbose:
                        print('[DEBUG] Testing https mode proxy')
                    sesi.get('http://httpbin.org/get')
                    pmode = "HTTPS/SOCKS5"
                except:
                    if args.verbose:
                        print('[DEBUG] Failed')
                    print('[ERROR] Cannot connect to proxy (Request timeout)')
                    sys.exit(1)
    else:
        sesi = requests.Session()
        try:
            sesi.get('http://httpbin.org/get')
            pmode = "No proxy"
        except:
            print('[ERROR] No connection available to make requests')
            sys.exit(0)
    if args.verbose:
        print('[DEBUG] Using proxy mode: {}'.format(pmode))
		
    print('[INFO] Fetching user token')
    authtoken = getAuthToken(sesi, args.verbose)
    sesi.headers.update({'Authorization': authtoken[0]})
	
    if args.input[-5:] != '.m3u8':
        print('[INFO] Parsing website')
        outputtitle, m3u8link = webparse(args.input, args.res, sesi, args.verbose)
        print('[INFO] Parsing m3u8')
        files, iv, ticket = parsem3u8(m3u8link, sesi, args.verbose)
        if args.output:
            if args.output[-3:] == '.ts':
                output = args.output
            else:
                output = args.output + '.ts'
        else:
            output = '{x} (AbemaTV {r}).ts'.format(x=outputtitle, r=args.res)
        if args.verbose:
            print('[DEBUG] Output file: {}'.format(output))
    elif args.input[-5:] == '.m3u8':
        print('[INFO] Parsing m3u8')
        outputtitle, res = webparse_m3u8(args.input, sesi, args.verbose)
        files, iv, ticket = parsem3u8(args.input, sesi, args.verbose)
        if args.output:
            if args.output[-3:] == '.ts':
                output = args.output
            else:
                output = args.output + '.ts'
        else:
            output = '{x} (AbemaTV {r}).ts'.format(x=outputtitle, r=res)

    # Don't use forbidden/illegal character (replace it with underscore)
    illegalchar = ['/', '<', '>', ':', '"', '\\', '|', '?', '*'] # https://docs.microsoft.com/en-us/windows/desktop/FileIO/naming-a-file
    for char in illegalchar:
        output = output.replace(char, '_')

    print('[INFO] Fetching video key')
    getkey = fetchVideoKey(ticket, authtoken, sesi, args.verbose)
    
    print('[INFO][DOWN] Starting downloader...')
    dllist, tempdir = getVideo(files, getkey, iv, sesi, args.verbose)
    print('[INFO][DOWN] Finished downloading')
    print('[INFO] Merging video')
    mergeVideo(dllist, output)
    print('[INFO] Finished merging')

    print('[INFO] Cleaning up')
    shutil.rmtree(tempdir)
    sys.exit(0)

if __name__=='__main__':
    main()