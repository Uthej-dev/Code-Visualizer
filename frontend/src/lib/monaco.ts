import { loader } from '@monaco-editor/react';
import * as monaco from 'monaco-editor';
import EditorWorker from 'monaco-editor/esm/vs/editor/editor.worker?worker';

// Use the locally bundled Monaco instead of loading it from a CDN.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() };
loader.config({ monaco });

monaco.editor.defineTheme('pystep-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    { token: 'comment', foreground: '6b7a90', fontStyle: 'italic' },
    { token: 'keyword', foreground: 'c4a7ff' },
    { token: 'string', foreground: '9fe0b4' },
    { token: 'number', foreground: 'f5c08b' },
  ],
  colors: {
    'editor.background': '#0c111b',
    'editor.lineHighlightBackground': '#00000000',
    'editor.lineHighlightBorder': '#00000000',
    'editorLineNumber.foreground': '#3b4760',
    'editorLineNumber.activeForeground': '#94a3b8',
    'editorGutter.background': '#0c111b',
    'editor.selectionBackground': '#2a3a5c',
    'editorIndentGuide.background1': '#1e2738',
    'editorCursor.foreground': '#7dd3fc',
    'scrollbarSlider.background': '#2a354966',
  },
});

export { monaco };
