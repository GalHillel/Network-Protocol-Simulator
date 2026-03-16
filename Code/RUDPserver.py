import socket
import requests
import mimetypes
from urllib.parse import urlparse
from pathlib import Path

# Define additional file types
mimetypes.types_map['.pdf'] = 'application/pdf'
mimetypes.types_map['.zip'] = 'application/zip'
mimetypes.types_map['.docx'] = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
mimetypes.types_map['.jpg'] = 'image/jpeg'
mimetypes.types_map['.jpeg'] = 'image/jpeg'
mimetypes.types_map['.png'] = 'image/png'
mimetypes.types_map['.gif'] = 'image/gif'
mimetypes.types_map['.bmp'] = 'image/bmp'
mimetypes.types_map['.doc'] = 'application/msword'
mimetypes.types_map['.txt'] = 'text/plain'
mimetypes.types_map['.csv'] = 'text/csv'
mimetypes.types_map['.mp3'] = 'audio/mpeg'
mimetypes.types_map['.wav'] = 'audio/wav'
mimetypes.types_map['.avi'] = 'video/x-msvideo'
mimetypes.types_map['.mp4'] = 'video/mp4'
mimetypes.types_map['.mkv'] = 'video/x-matroska'


def download_file(url, filename):
    parsed_url = urlparse(url)

    if not all([parsed_url.scheme, parsed_url.netloc]):
        return 'Please enter a valid URL'

    try:
        response = requests.get(url, stream=True)
        content_type = response.headers.get('Content-Type')

        extension = mimetypes.guess_extension(content_type)
        filename = filename + extension if extension else filename

        with open(filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    f.write(chunk)
                    f.flush()

        return f'Download complete. File saved as {filename}.'
    except Exception as e:
        return str(e)


serversocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
print("Server listening... ")

host = socket.gethostname()

port = 7878

# bind the socket to a public host, and a port
serversocket.bind((host, port))

while True:
    data, client_address = serversocket.recvfrom(1024)
    print(f"Got a connection from {client_address[0]}:{client_address[1]}")

    data = data.decode('utf-8').split(',')
    if len(data) != 2:
        response = 'Invalid request. Please provide a URL and a filename.'
    else:
        url, filename = data

        if Path(filename).exists():
            response = f'File {filename} already exists on the server.'
        else:
            try:
                response = download_file(url, filename)
            except Exception as e:
                response = str(e)

    # send response to client
    serversocket.sendto(response.encode('utf-8'), client_address)
