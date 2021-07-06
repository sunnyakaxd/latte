from aiohttp import web
from aiohttp.web import StreamResponse, Response
from mimetypes import MimeTypes
import asyncio

mimetypes = MimeTypes()
routes = web.RouteTableDef()

async def init_app():
	app = web.Application()
	app.add_routes(routes)
	return app

def requesthandler(fn):
	async def decorated(request):
		try:
			return await fn(request)
		except Exception as e:
			return Response(status=500)
	return decorated


CHUNK_SIZE = 512*1024*2

@routes.get('/private/files/{filename}')
@requesthandler
async def download(request):
	filename = request.match_info['filename']
	print('Filename:', filename)
	response = StreamResponse()
	response.content_type = mimetypes.guess_type(filename)
	response.headers.add('Content-Disposition', f'inline; filename={filename}')
	await response.prepare(request)
	with open(f'../sites/wra.ntex.com/private/files/{filename}', 'rb') as file_obj:
		while line := file_obj.read(CHUNK_SIZE):
			print('Sleeping')
			await asyncio.sleep(3)
			await response.write(line)
	await response.write_eof()
	return response