figma.showUI(__html__, { width: 220, height: 60, position: { x: 0, y: 0 } });

figma.ui.onmessage = async (msg) => {
    if (msg.type === "ready") {
        const savedId = await figma.clientStorage.getAsync("userId");
        figma.ui.postMessage({ type: "saved-id", userId: savedId || "" });
    }

    if (msg.type === "save-id") {
        await figma.clientStorage.setAsync("userId", msg.userId);
    }

    if (msg.type === "close") figma.closePlugin();

    // ── Текст ──────────────────────────────────────────────────────────────
    if (msg.type === "change-text") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && node.type === "TEXT") {
            await figma.loadFontAsync(node.fontName);
            node.characters = msg.text;
            figma.notify("Текст изменён ✔");
        }
    }

    // ── Цвет заливки ───────────────────────────────────────────────────────
    if (msg.type === "change-color") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && "fills" in node) {
            node.fills = [{ type: "SOLID", color: msg.color }];
            figma.notify("Цвет изменён ✔");
        }
    }

    // ── Шрифт / стиль текста ───────────────────────────────────────────────
    // msg: { nodeId, family?, style?, size?, color? }
    if (msg.type === "change-font") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && node.type === "TEXT") {
            const family = msg.family || node.fontName.family;
            const style  = msg.style  || node.fontName.style;
            await figma.loadFontAsync({ family, style });
            node.fontName = { family, style };
            if (msg.size)  node.fontSize = msg.size;
            if (msg.color) node.fills = [{ type: "SOLID", color: msg.color }];
            figma.notify("Шрифт изменён ✔");
        }
    }

    // ── Диагностика узла ──────────────────────────────────────────────────
    if (msg.type === "debug-node") {
        const node = figma.getNodeById(msg.nodeId);
        if (!node) {
            figma.notify(`❌ nodeId не найден: ${msg.nodeId}`);
            figma.ui.postMessage({ type: "response", requestType: "debug-node", found: false, nodeId: msg.nodeId });
        } else {
            figma.notify(`✔ Найден: ${node.name} [${node.type}]`);
            figma.ui.postMessage({ type: "response", requestType: "debug-node", found: true, nodeId: msg.nodeId, name: node.name, nodeType: node.type, x: node.x, y: node.y });
        }
    }

    // ── Перемещение ────────────────────────────────────────────────────────
    // msg: { nodeId, x, y }
    if (msg.type === "move") {
        const node = figma.getNodeById(msg.nodeId);
        if (!node) { figma.notify(`❌ move: узел не найден ${msg.nodeId}`); return; }
        if (!("x" in node)) { figma.notify(`❌ move: у узла нет x (${node.type})`); return; }
        if (msg.x !== undefined) node.x = msg.x;
        if (msg.y !== undefined) node.y = msg.y;
        figma.notify(`✔ Перемещено → ${node.x}, ${node.y}`);
    }

    // ── Изменение размера ──────────────────────────────────────────────────
    // msg: { nodeId, width?, height? }
    if (msg.type === "resize") {
        const node = figma.getNodeById(msg.nodeId);
        if (!node) { figma.notify(`❌ resize: узел не найден ${msg.nodeId}`); return; }
        if (!("resize" in node)) { figma.notify(`❌ resize: тип ${node.type} не поддерживает resize`); return; }
        const w = msg.width  || node.width;
        const h = msg.height || node.height;
        node.resize(w, h);
        figma.notify(`✔ Размер → ${w}x${h}`);
    }

    // ── Выравнивание ───────────────────────────────────────────────────────
    // msg: { nodeIds: [...], axis: "horizontal"|"vertical", align: "min"|"center"|"max" }
    if (msg.type === "align") {
        const nodes = (msg.nodeIds || []).map(id => figma.getNodeById(id)).filter(Boolean);
        if (nodes.length === 0) return;
        if (msg.axis === "horizontal") {
            const refs = nodes.map(n => n.x);
            let target;
            if (msg.align === "min")    target = Math.min(...refs);
            else if (msg.align === "max") target = Math.max(...refs.map((x, i) => x + nodes[i].width)) - nodes[0].width;
            else target = nodes.reduce((s, n) => s + n.x + n.width / 2, 0) / nodes.length;
            nodes.forEach(n => {
                if (msg.align === "center") n.x = target - n.width / 2;
                else n.x = target;
            });
        } else {
            const refs = nodes.map(n => n.y);
            let target;
            if (msg.align === "min")    target = Math.min(...refs);
            else if (msg.align === "max") target = Math.max(...refs.map((y, i) => y + nodes[i].height)) - nodes[0].height;
            else target = nodes.reduce((s, n) => s + n.y + n.height / 2, 0) / nodes.length;
            nodes.forEach(n => {
                if (msg.align === "center") n.y = target - n.height / 2;
                else n.y = target;
            });
        }
        figma.notify("Выровнено ✔");
    }

    // ── Авто-layout ────────────────────────────────────────────────────────
    // msg: { nodeId, direction: "HORIZONTAL"|"VERTICAL"|"NONE", spacing?, padding?, wrap? }
    if (msg.type === "set-autolayout") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && "layoutMode" in node) {
            node.layoutMode = msg.direction || "HORIZONTAL";
            if (msg.spacing !== undefined)       node.itemSpacing = msg.spacing;
            if (msg.padding !== undefined)       node.paddingLeft = node.paddingRight = node.paddingTop = node.paddingBottom = msg.padding;
            if (msg.wrap !== undefined)          node.layoutWrap = msg.wrap ? "WRAP" : "NO_WRAP";
            figma.notify("Auto-layout применён ✔");
        }
    }

    // ── Эффекты (тень, blur) ────────────────────────────────────────────────
    // msg: { nodeId, effects: [ { type: "DROP_SHADOW"|"INNER_SHADOW"|"LAYER_BLUR"|"BACKGROUND_BLUR", ... } ] }
    if (msg.type === "set-effects") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && "effects" in node) {
            node.effects = msg.effects;
            figma.notify("Эффекты применены ✔");
        }
    }

    // ── Обводка (stroke) ────────────────────────────────────────────────────
    // msg: { nodeId, color, weight? }
    if (msg.type === "set-stroke") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && "strokes" in node) {
            node.strokes = [{ type: "SOLID", color: msg.color }];
            if (msg.weight !== undefined) node.strokeWeight = msg.weight;
            figma.notify("Обводка задана ✔");
        }
    }

    // ── Скругление углов ────────────────────────────────────────────────────
    // msg: { nodeId, radius }
    if (msg.type === "set-corner-radius") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && "cornerRadius" in node) {
            node.cornerRadius = msg.radius;
            figma.notify("Скругление задано ✔");
        }
    }

    // ── Создать прямоугольник ──────────────────────────────────────────────
    if (msg.type === "create-rect") {
        const rect = figma.createRectangle();
        rect.resize(msg.width || 200, msg.height || 100);
        rect.fills = [{ type: "SOLID", color: msg.color || { r: 0.2, g: 0.6, b: 1 } }];
        if (msg.x !== undefined) rect.x = msg.x;
        if (msg.y !== undefined) rect.y = msg.y;
        if (msg.name) rect.name = msg.name;
        figma.currentPage.appendChild(rect);
        figma.notify("Прямоугольник создан ✔");
    }

    // ── Создать текстовый элемент ──────────────────────────────────────────
    // msg: { text, x?, y?, size?, family?, style?, color?, name? }
    if (msg.type === "create-text") {
        const text = figma.createText();
        const family = msg.family || "Inter";
        const style  = msg.style  || "Regular";
        await figma.loadFontAsync({ family, style });
        text.characters = msg.text || "Text";
        text.fontName = { family, style };
        if (msg.size)  text.fontSize = msg.size;
        if (msg.color) text.fills = [{ type: "SOLID", color: msg.color }];
        if (msg.x !== undefined) text.x = msg.x;
        if (msg.y !== undefined) text.y = msg.y;
        if (msg.name) text.name = msg.name;
        figma.currentPage.appendChild(text);
        figma.notify("Текст создан ✔");
    }

    // ── Создать фрейм ─────────────────────────────────────────────────────
    // msg: { width?, height?, x?, y?, name?, color? }
    if (msg.type === "create-frame") {
        const frame = figma.createFrame();
        frame.resize(msg.width || 400, msg.height || 300);
        if (msg.x !== undefined) frame.x = msg.x;
        if (msg.y !== undefined) frame.y = msg.y;
        if (msg.name) frame.name = msg.name;
        if (msg.color) frame.fills = [{ type: "SOLID", color: msg.color }];
        figma.currentPage.appendChild(frame);
        figma.notify("Фрейм создан ✔");
    }

    // ── Удалить элемент ───────────────────────────────────────────────────
    // msg: { nodeId }
    if (msg.type === "delete-node") {
        const node = figma.getNodeById(msg.nodeId);
        if (node && node.type !== "PAGE" && node.type !== "DOCUMENT") {
            node.remove();
            figma.notify("Удалено ✔");
        }
    }

    // ── Получить узлы страницы (без REST API) ─────────────────────────────
    // msg: { nameFilter?: string }  → возвращает массив { id, name, type, x, y, width, height }
    if (msg.type === "get-page-nodes") {
        const filter = msg.nameFilter ? msg.nameFilter.toLowerCase() : null;
        const result = [];
        function collect(node) {
            if (!filter || node.name.toLowerCase().includes(filter)) {
                const entry = { id: node.id, name: node.name, type: node.type };
                if ("x" in node)      { entry.x = node.x; entry.y = node.y; }
                if ("width" in node)  { entry.width = node.width; entry.height = node.height; }
                result.push(entry);
            }
            if ("children" in node) node.children.forEach(collect);
        }
        figma.currentPage.children.forEach(collect);
        figma.ui.postMessage({ type: "response", requestType: "get-page-nodes", nodes: result });
    }

    // ── Переименовать элемент ─────────────────────────────────────────────
    // msg: { nodeId, name }
    if (msg.type === "rename") {
        const node = figma.getNodeById(msg.nodeId);
        if (node) {
            node.name = msg.name;
            figma.notify("Переименовано ✔");
        }
    }

    // ── Добавить элемент внутрь другого (append) ──────────────────────────
    // msg: { nodeId, parentId }
    if (msg.type === "append-to") {
        const node   = figma.getNodeById(msg.nodeId);
        const parent = figma.getNodeById(msg.parentId);
        if (node && parent && "appendChild" in parent) {
            parent.appendChild(node);
            figma.notify("Перемещено в родителя ✔");
        }
    }
};
