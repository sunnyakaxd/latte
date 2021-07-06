function handleFailedResponse(event, response) {
  // console.log(response);
  return caches.match(event.request).then(function (cachedResponse) {
    // Cache hit - return response
    if (cachedResponse) {
      // console.log("Returning cached response");
      return cachedResponse;
    }
    // console.log("Returning original failed response");
    return response;
  });
}

function networkFirst(event) {
  return fetch(event.request)
    .then(function (response) {
      // Check if we received a valid response
      // console.log(response.status, response.type);
      if (!response || response.status !== 200 || response.type !== "basic") {
        return handleFailedResponse(event, response);
      } else if (
        response &&
        response.status === 200 &&
        response.type === "basic"
      ) {
        // console.log("Caching response");
        var responseToCache = response.clone();

        caches.open(CACHE_NAME).then(function (cache) {
          cache.put(event.request, responseToCache);
        });
        return response;
      } else {
        // console.log("Returning original non basic response");
        return response;
      }
    })
    .catch((response) => {
      return handleFailedResponse(event, response);
    });
}

function refreshCache(event) {
  return fetch(event.request).then(function (response) {
    // Check if we received a valid response
    if (!response || response.status !== 200 || response.type !== "basic") {
      return response;
    }

    // IMPORTANT: Clone the response. A response is a stream
    // and because we want the browser to consume the response
    // as well as the cache consuming the response, we need
    // to clone it so we have two streams.
    var responseToCache = response.clone();

    caches.open(CACHE_NAME).then(function (cache) {
      cache.put(event.request, responseToCache);
    });

    return response;
  });
}

function cacheFirst(event) {
  return caches.match(event.request).then(function (response) {
    // Cache hit - return response
    if (response) {
      setTimeout(() => refreshCache(event), 0);
      return response;
    }

    return refreshCache(event);
  });
}

STRATEGY = {
  cacheFirst,
  networkFirst,
};

const pathsToCache = {
  "/desk": cacheFirst,
  "/api/method/latte.dashboard.doctype.dashboard_data_slice.run": networkFirst,
  "/api/method/frappe.desk.doctype.desktop_icon.desktop_icon.get_module_icons": cacheFirst,
  "/api/method/frappe.core.doctype.user_permission.user_permission.get_user_permissions": cacheFirst,
  "/api/method/frappe.desk.desk_page.getpage": cacheFirst,
  "/api/method/frappe.desk.form.load.getdoc": networkFirst,
  "/api/method/frappe.client.get": networkFirst,
  "/api/method/frappe.client.get_value": networkFirst,
  "/api/method/frappe.model.db_query.get_list": networkFirst,
  "/api/method/latte.dashboard.doctype.dashboard_configuration.dashboard_access": cacheFirst,
  "/api/method/frappe.desk.moduleview.get": cacheFirst,
};

const regexCache = [
  [/^.*\.js$/, cacheFirst],
  [/^.*\.css$/, cacheFirst],
  [/^.*\.mp3$/, cacheFirst],
  [/^.*\.svg$/, cacheFirst],
  [/^.*\.woff[2]?$/, cacheFirst],
];

const CACHE_NAME = "latte-cache";

self.addEventListener("fetch", function (event) {
  if (event.request.method != "GET") {
    return;
  }
  const urlMeta = new URL(event.request.url);
  const uriPath = urlMeta.pathname;
  let strategy = pathsToCache[uriPath];
  if (!strategy) {
    for (const [regex, regexStrategy] of regexCache) {
      if (uriPath.match(regex)) {
        strategy = regexStrategy;
        break;
      }
    }
    // console.log(uriPath, strategy?.name);
    return strategy && event.respondWith(strategy(event));
  }
  // console.log(uriPath, strategy?.name);
  return event.respondWith(strategy(event));
});

fetch("/api/method/latte.get_installed_apps").then((res) => {
  res.json().then((resJson) => {
    const apps = resJson.message;
    apps.forEach((app) => {
      fetch(`/assets/${app}/sw-cache-config.js`).then((res) => {
        if (res.status != 200) {
          return;
        }
        res.text().then((script) => {
          eval(script);
        });
      });
    });
  });
});
