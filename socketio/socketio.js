const app = require("express")();
const server = require("http").Server(app);
const io = require("socket.io")(server);
const request = require("superagent");
const {
  get_path,
  get_conf,
  get_redis_subscriber,
  get_redis_cache,
} = require("./node_utils");
const uuid = require("uuid");

const { ArgumentParser } = require('argparse');

const parser = new ArgumentParser({
  description: 'Argparse example'
});

parser.add_argument('-p', '--port', { help: 'port' });
parser.add_argument('-b', '--bind-socket', { help: 'unix socket' });

let {port, bind_socket} = parser.parse_args();
if (port) {
  port = parseInt(port);
}

if (bind_socket) {
  bind_socket = get_path(bind_socket);
}

var conf = get_conf();
var subscriber = get_redis_subscriber();
var cache = get_redis_cache();
// serve socketio
const listenOn = port || bind_socket || conf.socketio_port;
console.log('Establishing listener on', listenOn);
server.listen(listenOn, function () {
  console.log("listening on *:", listenOn); //eslint-disable-line
});

// on socket connection
io.on("connection", function (socket) {
  // console.log('conn', socket.handshake.query, socket.handshake.headers);
  const { cookie } = socket.handshake.headers;
  const { origin } = socket.handshake.query;

  if (!(cookie && origin)) {
    return socket.disconnect();
  }

  for (const scookie of cookie.split(';')) {
    const [cookie_name, cookie_val] = scookie.trim().split('=');
    if (cookie_name.trim().toLocaleLowerCase() === 'user_id' && cookie_val.trim().toLocaleLowerCase() === 'guest') {
      return socket.disconnect();
    }
  }

  socket.cookie = cookie;
  socket.origin = origin;
  request
    .get(get_url(socket, "/api/method/latte.whoami"))
    .type("json")
    .set("cookie", cookie)
    .end(function (err, res) {
      if (err) {
        console.log(err);
        return;
      }

      if (res.status == 200) {
        initSocket(socket);
        socket.user = res.body.message;
        var room = get_user_room(socket, socket.user);
        console.log("Room", room);
        socket.join(room);
        socket.join(get_site_room(socket));
      }
    });
});

function initSocket(socket) {
  // socket.user = cookie.parse(socket.request.headers.cookie).user_id;
  socket.files = {};

  // frappe.chat
  socket.on("frappe.chat.room:subscribe", function (rooms) {
    if (!Array.isArray(rooms)) {
      rooms = [rooms];
    }

    for (var room of rooms) {
      console.log(
        "frappe.chat: Subscribing " + socket.user + " to room " + room
      );
      room = get_chat_room(socket, room);

      console.log(
        "frappe.chat: Subscribing " + socket.user + " to event " + room
      );
      socket.join(room);
    }
  });

  socket.on("frappe.chat.message:typing", function (data) {
    const user = data.user;
    const room = get_chat_room(socket, data.room);

    console.log("frappe.chat: Dispatching " + user + " typing to room " + room);

    io.to(room).emit("frappe.chat.room:typing", {
      room: data.room,
      user: user,
    });
  });
  // end frappe.chat

  socket.on("disconnect", function () {
    delete socket.files;
  });

  socket.on("task_subscribe", function (task_id) {
    var room = get_task_room(socket, task_id);
    socket.join(room);
  });

  socket.on("task_unsubscribe", function (task_id) {
    var room = get_task_room(socket, task_id);
    socket.leave(room);
  });

  socket.on("progress_subscribe", function (task_id) {
    var room = get_task_room(socket, task_id);
    socket.join(room);
    send_existing_lines(task_id, socket);
  });

  socket.on("doc_subscribe", function (doctype, docname) {
    can_subscribe_doc({
      socket: socket,
      doctype: doctype,
      docname: docname,
      callback: function (err, res) {
        var room = get_doc_room(socket, doctype, docname);
        socket.join(room);
      },
    });
  });

  socket.on("doc_unsubscribe", function (doctype, docname) {
    var room = get_doc_room(socket, doctype, docname);
    socket.leave(room);
  });

  socket.on("task_unsubscribe", function (task_id) {
    var room = "task:" + task_id;
    socket.leave(room);
  });

  socket.on("doc_open", function (doctype, docname) {
    // show who is currently viewing the form
    can_subscribe_doc({
      socket: socket,
      doctype: doctype,
      docname: docname,
      callback: function (err, res) {
        var room = get_open_doc_room(socket, doctype, docname);
        socket.join(room);

        send_viewers({
          socket: socket,
          doctype: doctype,
          docname: docname,
        });
      },
    });
  });

  socket.on("doc_close", function (doctype, docname) {
    // remove this user from the list of 'who is currently viewing the form'
    var room = get_open_doc_room(socket, doctype, docname);
    socket.leave(room);
    send_viewers({
      socket: socket,
      doctype: doctype,
      docname: docname,
    });
  });

  socket.on("upload-file-upload-chunk", (data) => {
    let fileCachePath;
    try {
      if (!data.upload_id) {
        throw new Error("Upload id is mandatory");
      }
      fileCachePath = `upload_file|${socket.user}|${data.upload_id}`;
      let fileObj = socket.files[data.upload_id];
      if (!fileObj) {
        fileObj = socket.files[data.upload_id] = {
          slice: 0,
          size: data.size,
        };
      }

      cache.lpush(fileCachePath, data.data);
      fileObj.slice++;

      if (fileObj.slice * 24576 >= fileObj.size) {
        socket.emit("upload-file-end", {
          upload_id: data.upload_id,
        });
      } else {
        socket.emit("upload-file-request-chunk", {
          upload_id: data.upload_id,
          currentSlice: fileObj.slice,
        });
      }
    } catch (e) {
      console.log(e);
      if (fileCachePath) {
        cache.del(fileCachePath);
      }
      socket.emit("upload-error", {
        error: e.message,
        upload_id: data.upload_id,
      });
    }
  });
}

subscriber.on("message", function (channel, message, room) {
  message = JSON.parse(message);

  if (message.room) {
    io.to(message.room).emit(message.event, message.message);
  } else {
    io.emit(message.event, message.message);
  }
});

subscriber.subscribe("events");

function send_existing_lines(task_id, socket) {
  var room = get_task_room(socket, task_id);
  subscriber.hgetall("task_log:" + task_id, function (err, lines) {
    io.to(room).emit("task_progress", {
      task_id: task_id,
      message: {
        lines: lines,
      },
    });
  });
}

function get_doc_room(socket, doctype, docname) {
  return get_site_name(socket) + ":doc:" + doctype + "/" + docname;
}

function get_open_doc_room(socket, doctype, docname) {
  return get_site_name(socket) + ":open_doc:" + doctype + "/" + docname;
}

function get_user_room(socket, user) {
  return get_site_name(socket) + ":user:" + user;
}

function get_site_room(socket) {
  return get_site_name(socket) + ":all";
}

function get_task_room(socket, task_id) {
  return get_site_name(socket) + ":task_progress:" + task_id;
}

// frappe.chat
// If you're thinking on multi-site or anything, please
// update frappe.async as well.
function get_chat_room(socket, room) {
  var room = get_site_name(socket) + ":room:" + room;

  return room;
}

function get_site_name(socket) {
  if (socket.request.headers["x-frappe-site-name"]) {
    return get_hostname(socket.request.headers["x-frappe-site-name"]);
  } else if (
    ["localhost", "127.0.0.1"].indexOf(socket.request.headers.host) !== -1 &&
    conf.default_site
  ) {
    // from currentsite.txt since host is localhost
    return conf.default_site;
  } else if (socket.request.headers.origin) {
    return get_hostname(socket.request.headers.origin);
  } else {
    return get_hostname(socket.request.headers.host);
  }
}

function get_hostname(url) {
  if (!url) return undefined;
  if (url.indexOf("://") > -1) {
    url = url.split("/")[2];
  }
  return url.match(/:/g) ? url.slice(0, url.indexOf(":")) : url;
}

function get_url(socket, path) {
  if (!path) {
    path = "";
  }
  if (!socket.web_discovery) {
    if (conf.web_discovery) {
      socket.web_discovery = conf.web_discovery;
    } else {
      socket.web_discovery = socket.origin;
    }
  }
  return socket.web_discovery + path;
}

function can_subscribe_doc(args) {
  if (!args) return;
  if (!args.doctype || !args.docname) return;
  request
    .get(get_url(args.socket, "/api/method/latte.realtime.can_subscribe_doc"))
    .type("json")
    .set('accept', 'application/json')
    .set('cookie', args.socket.cookie)
    .query({
      doctype: args.doctype,
      docname: args.docname,
    })
    .end(function (err, res) {
      if (!res) {
        console.log("No response for doc_subscribe");
      } else if (res.status == 403) {
        return;
      } else if (err) {
        console.log(err);
      } else if (res.status == 200) {
        args.callback(err, res);
      } else {
        console.log("Something went wrong", err, res);
      }
    });
}

function send_viewers(args) {
  // send to doc room, 'users currently viewing this document'
  if (!(args && args.doctype && args.docname)) {
    return;
  }

  // open doc room
  var room = get_open_doc_room(args.socket, args.doctype, args.docname);

  var socketio_room = io.sockets.adapter.rooms[room] || {};

  // for compatibility with both v1.3.7 and 1.4.4
  var clients_dict =
    "sockets" in socketio_room ? socketio_room.sockets : socketio_room;

  // socket ids connected to this room
  var clients = Object.keys(clients_dict || {});

  var viewers = [];
  for (var i in io.sockets.sockets) {
    var s = io.sockets.sockets[i];
    if (clients.indexOf(s.id) !== -1) {
      // this socket is connected to the room
      viewers.push(s.user);
    }
  }

  // notify
  io.to(room).emit("doc_viewers", {
    doctype: args.doctype,
    docname: args.docname,
    viewers: viewers,
  });
}
