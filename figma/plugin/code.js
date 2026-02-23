figma.showUI(__html__, { width: 220, height: 60, position: { x: 0, y: 0 } });

async function getNode(id) {
    return await figma.getNodeByIdAsync(id);
}

figma.ui.onmessage = async (msg) => {
    try {

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
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ change-text: узел не найден ${msg.nodeId}`); return; }
        if (node.type !== "TEXT") { figma.notify(`❌ change-text: не TEXT (${node.type})`); return; }
        if (node.fontName === figma.mixed) {
            const fonts = node.getRangeAllFontNames(0, node.characters.length);
            for (const font of fonts) await figma.loadFontAsync(font);
        } else {
            await figma.loadFontAsync(node.fontName);
        }
        node.characters = msg.text;
        figma.notify("Текст изменён ✔");
    }

    // ── Цвет заливки ───────────────────────────────────────────────────────
    if (msg.type === "change-color") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ change-color: узел не найден`); return; }
        if (!("fills" in node)) { figma.notify(`❌ change-color: нет fills у ${node.type}`); return; }
        node.fills = [{ type: "SOLID", color: msg.color }];
        figma.notify("Цвет изменён ✔");
    }

    // ── Шрифт ──────────────────────────────────────────────────────────────
    if (msg.type === "change-font") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ change-font: узел не найден`); return; }
        if (node.type !== "TEXT") { figma.notify(`❌ change-font: не TEXT`); return; }
        const family = msg.family || (node.fontName !== figma.mixed ? node.fontName.family : "Inter");
        const style  = msg.style  || (node.fontName !== figma.mixed ? node.fontName.style  : "Regular");
        await figma.loadFontAsync({ family, style });
        node.fontName = { family, style };
        if (msg.size  !== undefined) node.fontSize = msg.size;
        if (msg.color !== undefined) node.fills = [{ type: "SOLID", color: msg.color }];
        figma.notify("Шрифт изменён ✔");
    }

    // ── Диагностика узла ──────────────────────────────────────────────────
    if (msg.type === "debug-node") {
        const node = await getNode(msg.nodeId);
        if (!node) {
            figma.notify(`❌ nodeId не найден: ${msg.nodeId}`);
            figma.ui.postMessage({ type: "response", requestId: msg.requestId, requestType: "debug-node", found: false, nodeId: msg.nodeId });
        } else {
            figma.notify(`✔ Найден: ${node.name} [${node.type}]`);
            figma.ui.postMessage({ type: "response", requestId: msg.requestId, requestType: "debug-node", found: true, nodeId: msg.nodeId, name: node.name, nodeType: node.type, x: node.x, y: node.y });
        }
    }

    // ── Перемещение ────────────────────────────────────────────────────────
    if (msg.type === "move") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ move: узел не найден`); return; }
        if (!("x" in node)) { figma.notify(`❌ move: нет координат у ${node.type}`); return; }
        if (msg.x !== undefined) node.x = msg.x;
        if (msg.y !== undefined) node.y = msg.y;
        figma.notify(`✔ Перемещено: ${node.name} → (${node.x}, ${node.y})`);
    }

    // ── Изменение размера ──────────────────────────────────────────────────
    if (msg.type === "resize") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ resize: узел не найден`); return; }
        if (typeof node.resize !== "function") { figma.notify(`❌ resize: не поддерживается (${node.type})`); return; }
        const w = msg.width  !== undefined ? msg.width  : node.width;
        const h = msg.height !== undefined ? msg.height : node.height;
        node.resize(w, h);
        figma.notify(`✔ Размер: ${node.name} → ${w}x${h}`);
    }

    // ── Выравнивание ───────────────────────────────────────────────────────
    if (msg.type === "align") {
        const ids = msg.nodeIds || [];
        if (ids.length === 0) { figma.notify("❌ align: нет nodeIds"); return; }
        const resolved = await Promise.all(ids.map(id => getNode(id)));
        const nodes = resolved.filter(n => n && "x" in n);
        if (nodes.length === 0) { figma.notify("❌ align: узлы не найдены"); return; }
        if (msg.axis === "horizontal") {
            if (msg.align === "min") {
                const t = Math.min(...nodes.map(n => n.x));
                nodes.forEach(n => { n.x = t; });
            } else if (msg.align === "max") {
                const t = Math.max(...nodes.map(n => n.x + (n.width || 0)));
                nodes.forEach(n => { n.x = t - (n.width || 0); });
            } else {
                const t = nodes.reduce((s, n) => s + n.x + (n.width || 0) / 2, 0) / nodes.length;
                nodes.forEach(n => { n.x = t - (n.width || 0) / 2; });
            }
        } else {
            if (msg.align === "min") {
                const t = Math.min(...nodes.map(n => n.y));
                nodes.forEach(n => { n.y = t; });
            } else if (msg.align === "max") {
                const t = Math.max(...nodes.map(n => n.y + (n.height || 0)));
                nodes.forEach(n => { n.y = t - (n.height || 0); });
            } else {
                const t = nodes.reduce((s, n) => s + n.y + (n.height || 0) / 2, 0) / nodes.length;
                nodes.forEach(n => { n.y = t - (n.height || 0) / 2; });
            }
        }
        figma.notify(`✔ Выровнено ${nodes.length} эл.`);
    }

    // ── Авто-layout ────────────────────────────────────────────────────────
    if (msg.type === "set-autolayout") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ set-autolayout: узел не найден`); return; }
        if (!("layoutMode" in node)) { figma.notify(`❌ set-autolayout: нужен FRAME, а не ${node.type}`); return; }
        node.layoutMode = msg.direction || "HORIZONTAL";
        if (msg.spacing !== undefined) node.itemSpacing = msg.spacing;
        if (msg.padding !== undefined) {
            node.paddingLeft = node.paddingRight = node.paddingTop = node.paddingBottom = msg.padding;
        }
        if (msg.paddingLeft   !== undefined) node.paddingLeft   = msg.paddingLeft;
        if (msg.paddingRight  !== undefined) node.paddingRight  = msg.paddingRight;
        if (msg.paddingTop    !== undefined) node.paddingTop    = msg.paddingTop;
        if (msg.paddingBottom !== undefined) node.paddingBottom = msg.paddingBottom;
        if (msg.wrap !== undefined) node.layoutWrap = msg.wrap ? "WRAP" : "NO_WRAP";
        figma.notify(`✔ Auto-layout: ${node.name} (${node.layoutMode})`);
    }

    // ── Эффекты ────────────────────────────────────────────────────────────
    // Читает реальную структуру эффектов из Figma и отправляет боту
    if (msg.type === "get-effects") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ get-effects: узел не найден`); return; }
        const raw = JSON.parse(JSON.stringify(node.effects));
        figma.ui.postMessage({
            type: "response",
            requestId: msg.requestId,
            requestType: "get-effects",
            nodeId: msg.nodeId,
            nodeName: node.name,
            effects: raw,
        });
        figma.notify(`ℹ effects отправлены (${raw.length} шт)`);
    }

    // set-effects: применяет эффекты
    // Структура строго по тому что вернул get-effects
    if (msg.type === "set-effects") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ set-effects: узел не найден`); return; }
        if (!("effects" in node)) { figma.notify(`❌ set-effects: ${node.type} не поддерживает effects`); return; }
        if (!Array.isArray(msg.effects)) { figma.notify("❌ set-effects: effects должен быть массивом"); return; }

        // Проверяем что узел не внутри инстанса компонента — Figma запрещает менять такие узлы
        let ancestor = node.parent;
        while (ancestor) {
            if (ancestor.type === "INSTANCE") {
                figma.notify(`❌ set-effects: ${node.name} внутри инстанса компонента — применяй эффект к самому инстансу или к верхнеуровневому фрейму`, { timeout: 5000 });
                return;
            }
            ancestor = ancestor.parent;
        }

        // Строим эффекты точно по схеме get-effects (boundVariables обязателен!)
        const built = msg.effects.map(e => {
            if (e.type === "DROP_SHADOW" || e.type === "INNER_SHADOW") {
                const c = e.color || {};
                return {
                    type:           e.type,
                    visible:        e.visible !== undefined ? !!e.visible : true,
                    radius:         typeof e.radius === "number" ? e.radius : 8,
                    boundVariables: {},
                    color: {
                        r: typeof c.r === "number" ? c.r : 0,
                        g: typeof c.g === "number" ? c.g : 0,
                        b: typeof c.b === "number" ? c.b : 0,
                        a: typeof c.a === "number" ? c.a : 0.25,
                    },
                    offset: {
                        x: (e.offset && typeof e.offset.x === "number") ? e.offset.x : 0,
                        y: (e.offset && typeof e.offset.y === "number") ? e.offset.y : 4,
                    },
                    spread:               typeof e.spread === "number" ? e.spread : 0,
                    blendMode:            e.blendMode || "NORMAL",
                    showShadowBehindNode: e.showShadowBehindNode !== undefined ? !!e.showShadowBehindNode : false,
                };
            }
            if (e.type === "LAYER_BLUR" || e.type === "BACKGROUND_BLUR") {
                return {
                    type:           e.type,
                    visible:        e.visible !== undefined ? !!e.visible : true,
                    radius:         typeof e.radius === "number" ? e.radius : 4,
                    boundVariables: {},
                };
            }
            return e;
        });

        node.effects = built;
        figma.notify(`✔ Эффекты: ${node.name} (${built.length} шт)`);
    }

    // ── Обводка ────────────────────────────────────────────────────────────
    if (msg.type === "set-stroke") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ set-stroke: узел не найден`); return; }
        if (!("strokes" in node)) { figma.notify(`❌ set-stroke: ${node.type} не поддерживает strokes`); return; }
        node.strokes = [{ type: "SOLID", color: msg.color || { r: 0, g: 0, b: 0 } }];
        if (msg.weight !== undefined) node.strokeWeight = msg.weight;
        if (msg.align  !== undefined) node.strokeAlign  = msg.align;
        figma.notify(`✔ Обводка: ${node.name}`);
    }

    // ── Скругление углов ────────────────────────────────────────────────────
    if (msg.type === "set-corner-radius") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ set-corner-radius: узел не найден`); return; }
        if (!("cornerRadius" in node)) { figma.notify(`❌ set-corner-radius: ${node.type} не поддерживает cornerRadius`); return; }
        if (msg.radius !== undefined) node.cornerRadius = msg.radius;
        if (msg.topLeft     !== undefined && "topLeftRadius"     in node) node.topLeftRadius     = msg.topLeft;
        if (msg.topRight    !== undefined && "topRightRadius"    in node) node.topRightRadius    = msg.topRight;
        if (msg.bottomLeft  !== undefined && "bottomLeftRadius"  in node) node.bottomLeftRadius  = msg.bottomLeft;
        if (msg.bottomRight !== undefined && "bottomRightRadius" in node) node.bottomRightRadius = msg.bottomRight;
        figma.notify(`✔ Скругление: ${node.name}`);
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
        figma.viewport.scrollAndZoomIntoView([rect]);
        figma.notify(`✔ Rect создан: ${rect.name}`);
    }

    // ── Создать текст ──────────────────────────────────────────────────────
    if (msg.type === "create-text") {
        const text = figma.createText();
        const family = msg.family || "Inter";
        const style  = msg.style  || "Regular";
        await figma.loadFontAsync({ family, style });
        text.characters = msg.text || "Text";
        text.fontName = { family, style };
        if (msg.size  !== undefined) text.fontSize = msg.size;
        if (msg.color !== undefined) text.fills = [{ type: "SOLID", color: msg.color }];
        if (msg.x !== undefined) text.x = msg.x;
        if (msg.y !== undefined) text.y = msg.y;
        if (msg.name) text.name = msg.name;
        figma.currentPage.appendChild(text);
        figma.viewport.scrollAndZoomIntoView([text]);
        figma.notify(`✔ Текст создан: "${text.characters}"`);
    }

    // ── Создать фрейм ─────────────────────────────────────────────────────
    if (msg.type === "create-frame") {
        const frame = figma.createFrame();
        frame.resize(msg.width || 400, msg.height || 300);
        if (msg.x !== undefined) frame.x = msg.x;
        if (msg.y !== undefined) frame.y = msg.y;
        if (msg.name) frame.name = msg.name;
        if (msg.color) frame.fills = [{ type: "SOLID", color: msg.color }];
        figma.currentPage.appendChild(frame);
        figma.viewport.scrollAndZoomIntoView([frame]);
        figma.notify(`✔ Фрейм создан: ${frame.name}`);
    }

    // ── Удалить ───────────────────────────────────────────────────────────
    if (msg.type === "delete-node") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ delete-node: узел не найден`); return; }
        if (node.type === "PAGE" || node.type === "DOCUMENT") { figma.notify("❌ нельзя удалить PAGE/DOCUMENT"); return; }
        const name = node.name;
        node.remove();
        figma.notify(`✔ Удалено: ${name}`);
    }

    // ── Получить узлы страницы ────────────────────────────────────────────
    if (msg.type === "get-page-nodes") {
        const filter = msg.nameFilter ? msg.nameFilter.toLowerCase() : null;
        const result = [];
        function collect(node) {
            if (!filter || node.name.toLowerCase().includes(filter)) {
                const entry = { id: node.id, name: node.name, type: node.type };
                if ("x" in node)     { entry.x = node.x; entry.y = node.y; }
                if ("width" in node) { entry.width = node.width; entry.height = node.height; }
                if (node.parent && node.parent.type !== "PAGE") {
                    entry.parentId   = node.parent.id;
                    entry.parentName = node.parent.name;
                }
                result.push(entry);
            }
            if ("children" in node) node.children.forEach(collect);
        }
        figma.currentPage.children.forEach(collect);
        figma.ui.postMessage({ type: "response", requestId: msg.requestId, requestType: "get-page-nodes", nodes: result });
    }

    // ── Переименовать ─────────────────────────────────────────────────────
    if (msg.type === "rename") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ rename: узел не найден`); return; }
        const old = node.name;
        node.name = msg.name;
        figma.notify(`✔ Переименовано: "${old}" → "${node.name}"`);
    }

    // ── Append-to ─────────────────────────────────────────────────────────
    if (msg.type === "append-to") {
        const node   = await getNode(msg.nodeId);
        const parent = await getNode(msg.parentId);
        if (!node)   { figma.notify(`❌ append-to: узел не найден`); return; }
        if (!parent) { figma.notify(`❌ append-to: родитель не найден`); return; }
        if (!("appendChild" in parent)) { figma.notify(`❌ append-to: ${parent.type} не контейнер`); return; }
        parent.appendChild(node);
        figma.notify(`✔ "${node.name}" → "${parent.name}"`);
    }

    // ── Клонировать ───────────────────────────────────────────────────────
    if (msg.type === "clone") {
        const node = await getNode(msg.nodeId);
        if (!node) { figma.notify(`❌ clone: узел не найден`); return; }
        const clone = node.clone();
        const offsetX = msg.offsetX !== undefined ? msg.offsetX : 20;
        const offsetY = msg.offsetY !== undefined ? msg.offsetY : 20;
        if ("x" in clone) { clone.x = node.x + offsetX; clone.y = node.y + offsetY; }
        clone.name = msg.name || (node.name + " (copy)");
        if (msg.parentId) {
            const parent = await getNode(msg.parentId);
            if (!parent) { figma.notify(`❌ clone: родитель не найден`); return; }
            if (!("appendChild" in parent)) { figma.notify(`❌ clone: ${parent.type} не контейнер`); return; }
            parent.appendChild(clone);
        } else {
            (node.parent && "appendChild" in node.parent ? node.parent : figma.currentPage).appendChild(clone);
        }
        figma.viewport.scrollAndZoomIntoView([clone]);
        figma.ui.postMessage({ type: "response", requestId: msg.requestId, requestType: "clone", cloneId: clone.id, cloneName: clone.name, x: clone.x, y: clone.y });
        figma.notify(`✔ Клон: "${clone.name}"`);
    }

    // ── Выбрать элементы ─────────────────────────────────────────────────
    if (msg.type === "select-nodes") {
        const ids = msg.nodeIds || (msg.nodeId ? [msg.nodeId] : []);
        const resolved = await Promise.all(ids.map(id => getNode(id)));
        const nodes = resolved.filter(Boolean);
        if (nodes.length === 0) { figma.notify("❌ select-nodes: не найдено"); return; }
        figma.currentPage.selection = nodes;
        figma.viewport.scrollAndZoomIntoView(nodes);
        figma.notify(`✔ Выбрано ${nodes.length} эл.`);
    }

    } catch (err) {
        figma.notify(`❌ [${msg.type}]: ${err.message}`, { timeout: 5000 });
        console.error(`[${msg.type}]`, err);
    }
};