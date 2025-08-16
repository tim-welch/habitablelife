module.exports = async (params) => {
    const app = params.app;
    const vault = app.vault;
    const workspace = app.workspace;

    const activeLeaf = workspace.activeLeaf;
    if (!activeLeaf) return;

    const editor = activeLeaf.view.editor;
    const selectedText = editor.getSelection().trim();

    // Step 1 & 2: Determine the note title
    let noteTitle = selectedText || await app.plugins.plugins["quickadd"].api.inputPrompt("Enter new note title");

    if (!noteTitle) return; // user canceled

    // Step 3: Convert to valid filename
    const fileName = noteTitle.replace(/\s+/g, "_").replace(/[\\/:*?"<>|]/g, "");
    const filePath = fileName + ".md";

    // Step 4: Prepare new note content with backlink to current note
    const currentFile = activeLeaf.view.file;
    const currentFileName = currentFile.basename;
    const newNoteContent = `# ${noteTitle}\n\nLinked from: [[${currentFileName}]]`;

    // Step 5: Create the new note
    await vault.create(filePath, newNoteContent);

    // Step 6: Replace selection (or insert link) in current note
    const newLink = `[[${fileName}]]`;
    if (selectedText) {
        editor.replaceSelection(newLink);
    } else {
        editor.replaceRange(newLink, editor.getCursor());
    }
};
