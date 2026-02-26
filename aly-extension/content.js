chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "alyTranslate",
    title: "Translate with Aly",
    contexts: ["selection"]
  });
});

chrome.contextMenus.onClicked.addListener((info) => {
  chrome.storage.local.set({ selectedText: info.selectionText });
});