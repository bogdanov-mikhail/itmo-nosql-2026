(function () {
  "use strict";

  var START = { kind: "table", key: "mongo.spa.appointments" };
  var state = {
    root: null,
    direction: "down",
    depth: 3,
    pathMode: false,
    pathFrom: null,
    pathTo: null,
    searchTimer: null,
    selectToken: 0,
    loadToken: 0,
  };
  var cy = null;
  var els = {};

  function splitId(id) {
    var separator = id.indexOf(":");
    return { kind: id.slice(0, separator), key: id.slice(separator + 1) };
  }

  function encodeKey(key) {
    return encodeURIComponent(key);
  }

  function setStatus(text, kind) {
    els.status.textContent = text;
    els.status.className = "status" + (kind ? " " + kind : "");
  }

  function showError(error) {
    if (error && error.status === 404) {
      setStatus("Не найдено: " + error.message, "warn");
    } else if (error && error.status === 400) {
      setStatus("Некорректный запрос: " + error.message, "error");
    } else {
      setStatus(error && error.message ? error.message : "Ошибка запроса", "error");
    }
  }

  async function api(path) {
    var response;
    try {
      response = await fetch(path, { headers: { Accept: "application/json" } });
    } catch (networkError) {
      throw new Error("Сервер недоступен");
    }
    var body = null;
    try {
      body = await response.json();
    } catch (parseError) {
      body = null;
    }
    if (!response.ok) {
      var detail = body && body.detail ? body.detail : "HTTP " + response.status;
      var error = new Error(detail);
      error.status = response.status;
      throw error;
    }
    return body;
  }

  function initGraph() {
    if (!window.cytoscape) {
      setStatus("Не загрузилась библиотека Cytoscape", "error");
      return;
    }
    if (window.cytoscapeDagre) {
      window.cytoscapeDagre(window.cytoscape);
    }

    cy = window.cytoscape({
      container: els.graph,
      wheelSensitivity: 0.2,
      minZoom: 0.15,
      maxZoom: 2.5,
      style: [
        {
          selector: "node",
          style: {
            label: "data(label)",
            "font-size": 11,
            "font-weight": 500,
            color: "#ffffff",
            "text-valign": "center",
            "text-halign": "center",
            "text-wrap": "wrap",
            "text-max-width": "130px",
            padding: "8px",
            width: "label",
            height: "label",
            shape: "round-rectangle",
            "background-color": "#2563eb",
            "border-width": 2,
            "border-color": "#1e40af",
          },
        },
        {
          selector: 'node[kind = "dag"]',
          style: {
            shape: "diamond",
            "background-color": "#ea580c",
            "border-color": "#9a3412",
            padding: "14px",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": "#111827",
          },
        },
        {
          selector: "node.path",
          style: {
            "border-width": 4,
            "border-color": "#15803d",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.5,
            "line-color": "#94a3b8",
            "target-arrow-color": "#94a3b8",
            "target-arrow-shape": "triangle",
            "arrow-scale": 0.8,
            "curve-style": "bezier",
            label: "data(label)",
            "font-size": 8,
            color: "#64748b",
            "text-rotation": "autorotate",
            "text-background-color": "#ffffff",
            "text-background-opacity": 0.85,
            "text-background-padding": "1px",
          },
        },
        {
          selector: "edge.path",
          style: {
            width: 3,
            "line-color": "#15803d",
            "target-arrow-color": "#15803d",
            color: "#166534",
          },
        },
      ],
    });

    cy.on("tap", "node", function (event) {
      var data = event.target.data();
      selectNode(data).catch(showError);
      if (state.pathMode) {
        handlePathClick(data);
      }
    });

    cy.on("dbltap", "node", function (event) {
      if (state.pathMode) {
        return;
      }
      expandNeighbors(event.target.data()).catch(showError);
    });

    window.addEventListener("resize", function () {
      if (cy) {
        cy.resize();
      }
    });
  }

  function toElements(graph) {
    var nodes = graph.nodes.map(function (node) {
      return {
        data: {
          id: node.id,
          label: node.label || node.key,
          kind: node.kind,
          key: node.key,
        },
      };
    });
    var edges = graph.edges.map(function (edge, index) {
      return {
        data: {
          id: "e" + index + ":" + edge.source + "->" + edge.target,
          source: edge.source,
          target: edge.target,
          label: edge.mode || "",
        },
      };
    });
    return nodes.concat(edges);
  }

  function layout() {
    cy.layout({
      name: "dagre",
      rankDir: "LR",
      align: "UL",
      nodeSep: 24,
      rankSep: 64,
      edgeSep: 12,
      padding: 24,
      animate: false,
      fit: true,
    }).run();
  }

  function render(graph) {
    cy.elements().remove();
    cy.add(toElements(graph));
    layout();
  }

  async function loadLineage(kind, key, options) {
    options = options || {};
    var direction = options.direction || state.direction;
    var depth = options.depth || state.depth;
    var token = ++state.loadToken;
    setStatus("Загрузка…");
    var graph = await api(
      "/api/lineage/" +
        encodeKey(kind) +
        "/" +
        encodeKey(key) +
        "?direction=" +
        encodeURIComponent(direction) +
        "&depth=" +
        encodeURIComponent(depth)
    );
    if (token !== state.loadToken) {
      return;
    }
    state.root = { kind: kind, key: key };
    state.direction = direction;
    state.depth = depth;
    updateDirectionButtons();
    els.depth.value = String(depth);
    render(graph);
    var root = graph.nodes.filter(function (node) {
      return node.id === kind + ":" + key;
    })[0];
    if (root) {
      cy.getElementById(root.id).select();
      selectNode(root).catch(showError);
    }
    var suffix = graph.truncated ? " · подграф усечён" : "";
    setStatus(
      graph.nodes.length + " узлов, " + graph.edges.length + " связей" + suffix,
      graph.truncated ? "warn" : "ok"
    );
  }

  function propValue(value) {
    if (value === null || value === undefined) {
      return "—";
    }
    if (typeof value === "object") {
      return JSON.stringify(value);
    }
    return String(value);
  }

  function renderProperties(node) {
    els.props.classList.remove("empty");
    els.props.textContent = "";

    var head = document.createElement("div");
    head.className = "prop-head";

    var title = document.createElement("span");
    title.className = "prop-title";
    title.textContent = node.label || node.key;
    head.appendChild(title);

    var badge = document.createElement("span");
    badge.className = "badge" + (node.kind === "dag" ? " dag" : "");
    badge.textContent = node.kind === "dag" ? "DAG" : "Table";
    head.appendChild(badge);

    els.props.appendChild(head);

    Object.keys(node.props || {}).forEach(function (key) {
      var row = document.createElement("div");
      row.className = "prop-row";

      var name = document.createElement("span");
      name.className = "prop-key";
      name.textContent = key;

      var value = document.createElement("span");
      value.className = "prop-value";
      value.textContent = propValue(node.props[key]);

      row.appendChild(name);
      row.appendChild(value);
      els.props.appendChild(row);
    });

    var expand = document.createElement("button");
    expand.type = "button";
    expand.className = "expand";
    expand.textContent = "Показать соседей";
    expand.addEventListener("click", function () {
      expandNeighbors(node).catch(showError);
    });
    els.props.appendChild(expand);
  }

  async function selectNode(data) {
    var token = ++state.selectToken;
    var kind = data.kind || splitId(data.id).kind;
    var key = data.key || splitId(data.id).key;
    var node = await api(
      "/api/node/" + encodeKey(kind) + "/" + encodeKey(key)
    );
    if (token !== state.selectToken) {
      return;
    }
    renderProperties(node);
  }

  function updateDirectionButtons() {
    Array.prototype.forEach.call(
      document.querySelectorAll("[data-direction]"),
      function (button) {
        button.classList.toggle(
          "active",
          button.getAttribute("data-direction") === state.direction
        );
      }
    );
  }

  function updatePathChips() {
    els.pathFrom.textContent = "от: " + (state.pathFrom || "—");
    els.pathTo.textContent = "до: " + (state.pathTo || "—");
  }

  async function handlePathClick(data) {
    if (!state.pathFrom || (state.pathFrom && state.pathTo)) {
      state.pathFrom = data.id;
      state.pathTo = null;
      updatePathChips();
      setStatus("Выберите конечный узел пути");
      return;
    }
    if (data.id === state.pathFrom) {
      setStatus("Нужен другой узел", "warn");
      return;
    }
    state.pathTo = data.id;
    updatePathChips();
    await loadPath();
  }

  async function loadPath() {
    if (!state.pathFrom || !state.pathTo) {
      return;
    }
    var token = ++state.loadToken;
    setStatus("Ищу путь…");
    try {
      var graph = await api(
        "/api/path?from=" +
          encodeURIComponent(state.pathFrom) +
          "&to=" +
          encodeURIComponent(state.pathTo)
      );
      if (token !== state.loadToken) {
        return;
      }
      render(graph);
      cy.elements().addClass("path");
      setStatus("Путь: " + graph.edges.length + " переходов", "ok");
    } catch (error) {
      if (error.status === 404) {
        setStatus("Путь не найден", "warn");
        return;
      }
      throw error;
    }
  }

  async function expandNeighbors(data) {
    var kind = data.kind || splitId(data.id).kind;
    var key = data.key || splitId(data.id).key;
    var graph = await api(
      "/api/lineage/" +
        encodeKey(kind) +
        "/" +
        encodeKey(key) +
        "?direction=both&depth=1"
    );

    var existingNodes = new Set(cy.nodes().map(function (node) { return node.id(); }));
    var existingPairs = new Set(
      cy.edges().map(function (edge) {
        return edge.data("source") + "->" + edge.data("target");
      })
    );

    var newNodes = graph.nodes.filter(function (node) {
      return !existingNodes.has(node.id);
    });
    var returned = new Set(
      graph.nodes.map(function (node) { return node.id; })
    );

    var newEdges = graph.edges.filter(function (edge) {
      var pair = edge.source + "->" + edge.target;
      return (
        returned.has(edge.source) &&
        returned.has(edge.target) &&
        !existingPairs.has(pair)
      );
    });

    if (!newNodes.length && !newEdges.length) {
      setStatus("Новых соседей нет");
      return;
    }

    cy.add(toElements({ nodes: newNodes, edges: newEdges }));
    layout();
    var node = cy.getElementById(kind + ":" + key);
    if (node.length) {
      node.select();
    }
    setStatus(
      "Добавлено соседей: " + newNodes.length + ", связей: " + newEdges.length,
      "ok"
    );
  }

  function hideSearch() {
    els.searchResults.hidden = true;
    els.searchResults.textContent = "";
  }

  async function runSearch() {
    var query = els.search.value.trim();
    if (!query) {
      hideSearch();
      return;
    }
    var body = await api("/api/search?q=" + encodeURIComponent(query));
    els.searchResults.textContent = "";
    if (!body.results.length) {
      var empty = document.createElement("li");
      empty.className = "search-empty";
      empty.textContent = "Ничего не найдено";
      els.searchResults.appendChild(empty);
    } else {
      body.results.forEach(function (node) {
        var item = document.createElement("li");
        var button = document.createElement("button");
        button.type = "button";

        var label = document.createElement("span");
        label.className = "result-label";
        label.textContent = node.label || node.key;

        var key = document.createElement("span");
        key.className = "result-key";
        key.textContent = (node.kind === "dag" ? "DAG · " : "Table · ") + node.key;

        button.appendChild(label);
        button.appendChild(key);
        button.addEventListener("click", function () {
          hideSearch();
          els.search.value = node.label || node.key;
          selectNode(node).catch(showError);
          loadLineage(node.kind, node.key, {
            direction: node.kind === "dag" ? "both" : state.direction,
          }).catch(showError);
        });
        item.appendChild(button);
        els.searchResults.appendChild(item);
      });
    }
    els.searchResults.hidden = false;
  }

  function bindEvents() {
    els.search.addEventListener("input", function () {
      window.clearTimeout(state.searchTimer);
      state.searchTimer = window.setTimeout(function () {
        runSearch().catch(showError);
      }, 220);
    });

    els.search.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        hideSearch();
      }
      if (event.key === "Enter") {
        var first = els.searchResults.querySelector("button");
        if (first) {
          event.preventDefault();
          first.click();
        }
      }
    });

    document.addEventListener("click", function (event) {
      if (!els.searchWrap.contains(event.target)) {
        hideSearch();
      }
    });

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        state.pathFrom = null;
        state.pathTo = null;
        updatePathChips();
        hideSearch();
      }
    });

    Array.prototype.forEach.call(
      document.querySelectorAll("[data-direction]"),
      function (button) {
        button.addEventListener("click", function () {
          state.direction = button.getAttribute("data-direction");
          updateDirectionButtons();
          if (state.root) {
            loadLineage(state.root.kind, state.root.key, {
              direction: state.direction,
            }).catch(showError);
          }
        });
      }
    );

    els.depth.addEventListener("change", function () {
      state.depth = Number(els.depth.value);
      if (state.root) {
        loadLineage(state.root.kind, state.root.key, { depth: state.depth }).catch(
          showError
        );
      }
    });

    els.pathMode.addEventListener("click", function () {
      state.pathMode = !state.pathMode;
      els.pathMode.classList.toggle("active", state.pathMode);
      state.pathFrom = null;
      state.pathTo = null;
      updatePathChips();
      setStatus(
        state.pathMode
          ? "Режим пути: выберите начальный узел"
          : "Режим пути выключен"
      );
    });

    els.resetView.addEventListener("click", function () {
      state.pathFrom = null;
      state.pathTo = null;
      updatePathChips();
      cy.elements().removeClass("path");
      if (state.root) {
        loadLineage(state.root.kind, state.root.key).catch(showError);
      } else {
        cy.elements().remove();
        setStatus("Граф очищен");
      }
    });
  }

  function cacheElements() {
    els.graph = document.getElementById("graph");
    els.search = document.getElementById("search");
    els.searchResults = document.getElementById("search-results");
    els.searchWrap = els.search.closest(".search-wrap");
    els.status = document.getElementById("status");
    els.depth = document.getElementById("depth");
    els.pathMode = document.getElementById("path-mode");
    els.resetView = document.getElementById("reset-view");
    els.props = document.getElementById("props");
    els.pathFrom = document.getElementById("path-from");
    els.pathTo = document.getElementById("path-to");
  }

  document.addEventListener("DOMContentLoaded", function () {
    cacheElements();
    initGraph();
    bindEvents();
    updatePathChips();
    updateDirectionButtons();
    loadLineage(START.kind, START.key, { direction: "down", depth: 3 }).catch(
      showError
    );
  });
})();