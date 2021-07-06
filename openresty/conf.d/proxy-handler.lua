local cjson = require("cjson")

function load_api_content(meta)
    if meta["proto"] ~= nil then
        ngx.var.proto = meta.proto
    else
        ngx.var.proto = "https"
    end

    for header, _ in pairs(ngx.req.get_headers()) do
        ngx.req.clear_header(header)
    end

    for header, value in pairs(meta.headers) do
        ngx.req.set_header(header, value)
    end

    ngx.req.set_header('host', meta.proxy)

    ngx.var.proxy = meta.proxy
    ngx.var.proxy_uri = meta.proxy_uri

    -- ngx.log(ngx.STDERR, ngx.var.proto, "://", ngx.var.proxy, ngx.var.proxy_uri)
    -- ngx.log(ngx.STDERR, cjson.encode(ngx.req.get_headers()))

end

function load_content(res)
    meta = cjson.decode(res.body)
    if meta.load_type == 'api' then
        load_api_content(meta)
    elseif meta.load_type == 'file' then
        local file_path = "/"..meta.file_name
        -- ngx.log(ngx.STDERR, file_path, ngx.var.inside_try_files)
        if ngx.var.inside_try_files ~= "Yes" then
            ngx.req.set_uri(file_path, true)
        end
    end

    for header, value in pairs(meta.response_headers) do
        ngx.header[header] = value
    end
    ngx.var.resp_content_type = meta.response_headers['Content-Type']
end

local res = ngx.location.capture("/get_proxy_meta")
if res.status >= 200 and res.status < 300 then
    load_content(res)
else
    ngx.exit(res.status)
end