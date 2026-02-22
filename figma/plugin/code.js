// Показываем UI
figma.showUI(__html__, { width: 300, height: 200 });

// Обработка сообщений из UI
figma.ui.onmessage = async (msg) => {
  if (msg.type === "create-block") {
    const rect = figma.createRectangle();
    rect.resize(240, 120);

    rect.fills = [{
      type: "SOLID",
      color: { r: 0.2, g: 0.6, b: 1 }
    }];

    figma.currentPage.appendChild(rect);

    figma.notify("Блок создан ✔");
  }

  if (msg.type === "create-text") {
    const text = figma.createText();
    await figma.loadFontAsync({ family: "Inter", style: "Regular" });
    text.characters = "Новый текстовый блок";
    figma.currentPage.appendChild(text);

    figma.notify("Текст создан ✔");
  }

  if (msg.type === "close") {
    figma.closePlugin();
  }
};