import Editor, { type OnMount } from '@monaco-editor/react';
import { useEffect, useRef } from 'react';
import { monaco } from '../lib/monaco';

export interface EditorMarker {
  line: number;
  endLine?: number | null;
}

export interface EditorErrorMarker {
  line: number;
  column?: number | null;
  message: string;
}

interface Props {
  code: string;
  onChange: (code: string) => void;
  onRun: () => void;
  current: EditorMarker | null;
  next: EditorMarker | null;
  error: EditorErrorMarker | null;
  /** Changes on each step so the highlight animation restarts. */
  stepKey: number;
}

type MonacoEditor = monaco.editor.IStandaloneCodeEditor;

export function CodeEditor({ code, onChange, onRun, current, next, error, stepKey }: Props) {
  const editorRef = useRef<MonacoEditor | null>(null);
  const decorations = useRef<monaco.editor.IEditorDecorationsCollection | null>(null);
  const onRunRef = useRef(onRun);
  onRunRef.current = onRun;

  const handleMount: OnMount = (editor) => {
    editorRef.current = editor as unknown as MonacoEditor;
    decorations.current = editorRef.current.createDecorationsCollection();
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => onRunRef.current());
    applyDecorations();
  };

  const applyDecorations = () => {
    const editor = editorRef.current;
    const collection = decorations.current;
    if (!editor || !collection) return;
    const model = editor.getModel();
    if (!model) return;
    const lineCount = model.getLineCount();
    const valid = (l: number | null | undefined): l is number => typeof l === 'number' && l >= 1 && l <= lineCount;
    const items: monaco.editor.IModelDeltaDecoration[] = [];

    if (next && valid(next.line) && next.line !== current?.line) {
      items.push({
        range: new monaco.Range(next.line, 1, next.line, 1),
        options: { isWholeLine: true, glyphMarginClassName: 'cv-glyph-next', glyphMarginHoverMessage: { value: 'Next line to run' } },
      });
    }
    if (current && valid(current.line)) {
      const end = valid(current.endLine) && current.endLine >= current.line ? current.endLine : current.line;
      items.push({
        range: new monaco.Range(current.line, 1, end, 1),
        options: {
          isWholeLine: true,
          className: stepKey % 2 === 0 ? 'cv-line-current cv-anim-a' : 'cv-line-current cv-anim-b',
          linesDecorationsClassName: 'cv-line-bar',
        },
      });
      items.push({
        range: new monaco.Range(current.line, 1, current.line, 1),
        options: { glyphMarginClassName: 'cv-glyph-current', glyphMarginHoverMessage: { value: 'Line that just ran' } },
      });
    }
    if (error && valid(error.line)) {
      items.push({
        range: new monaco.Range(error.line, 1, error.line, model.getLineMaxColumn(error.line)),
        options: {
          isWholeLine: true,
          className: 'cv-line-error',
          after: { content: `   ⟵ ${error.message}`, inlineClassName: 'cv-inline-error' },
        },
      });
    }
    collection.set(items);
    monaco.editor.setModelMarkers(
      model,
      'pystep',
      error && valid(error.line)
        ? [{
            severity: monaco.MarkerSeverity.Error,
            message: error.message,
            startLineNumber: error.line,
            endLineNumber: error.line,
            startColumn: error.column ?? 1,
            endColumn: model.getLineMaxColumn(error.line),
          }]
        : [],
    );
    if (current && valid(current.line)) editor.revealLineInCenterIfOutsideViewport(current.line, monaco.editor.ScrollType.Smooth);
    else if (error && valid(error.line)) editor.revealLineInCenterIfOutsideViewport(error.line);
  };

  useEffect(applyDecorations, [current?.line, current?.endLine, next?.line, error?.line, error?.message, error?.column, stepKey, code]);

  return (
    <div className="h-full min-h-0" data-testid="code-editor">
      <Editor
        height="100%"
        defaultLanguage="python"
        language="python"
        theme="pystep-dark"
        value={code}
        onChange={(value) => onChange(value ?? '')}
        onMount={handleMount}
        loading={<div className="p-4 text-sm text-slate-500">Loading editor…</div>}
        options={{
          fontFamily: '"JetBrains Mono", ui-monospace, Menlo, monospace',
          fontSize: 14,
          lineHeight: 22,
          minimap: { enabled: false },
          glyphMargin: true,
          lineNumbersMinChars: 3,
          lineDecorationsWidth: 6,
          scrollBeyondLastLine: false,
          renderLineHighlight: 'none',
          smoothScrolling: true,
          padding: { top: 12, bottom: 12 },
          tabSize: 4,
          insertSpaces: true,
          automaticLayout: true,
          wordWrap: 'off',
          fixedOverflowWidgets: true,
          ariaLabel: 'Python code editor',
          scrollbar: { verticalScrollbarSize: 8, horizontalScrollbarSize: 8 },
        }}
      />
    </div>
  );
}
