import urllib.request

# Test without range (initial load)
req = urllib.request.Request("http://127.0.0.1:8765/api/songs/55/stream")
try:
    with urllib.request.urlopen(req) as r:
        print(f"No Range - Status: {r.status}")
        print(f"  Accept-Ranges: {r.getheader('Accept-Ranges')}")
        print(f"  Content-Type: {r.getheader('Content-Type')}")
        print(f"  Content-Length: {r.getheader('Content-Length')}")
        print(f"  Content-Range: {r.getheader('Content-Range')}")
except Exception as e:
    print(f"No Range Error: {e}")

# Test with range header
req2 = urllib.request.Request("http://127.0.0.1:8765/api/songs/55/stream")
req2.add_unredirected_header("Range", "bytes=0-65535")
try:
    with urllib.request.urlopen(req2) as r:
        print(f"\nWith Range bytes=0-65535 - Status: {r.status}")
        print(f"  Accept-Ranges: {r.getheader('Accept-Ranges')}")
        print(f"  Content-Type: {r.getheader('Content-Type')}")
        print(f"  Content-Length: {r.getheader('Content-Length')}")
        print(f"  Content-Range: {r.getheader('Content-Range')}")
except Exception as e:
    print(f"Range Error: {e}")
