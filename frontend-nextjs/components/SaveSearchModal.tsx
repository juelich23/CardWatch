'use client';

import { useState } from 'react';

interface SaveSearchModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSave: (name: string) => Promise<void>;
}

export function SaveSearchModal({ isOpen, onClose, onSave }: SaveSearchModalProps) {
  const [saveSearchName, setSaveSearchName] = useState('');
  const [saveError, setSaveError] = useState('');
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!saveSearchName.trim()) {
      setSaveError('Please enter a name for this search');
      return;
    }

    try {
      setIsSaving(true);
      setSaveError('');
      await onSave(saveSearchName.trim());
      setSaveSearchName('');
      onClose();
    } catch (err) {
      setSaveError(err instanceof Error ? err.message : 'Failed to save search');
    } finally {
      setIsSaving(false);
    }
  };

  const handleClose = () => {
    setSaveSearchName('');
    setSaveError('');
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={handleClose}>
      <div className="bg-panel border border-border rounded-lg p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
        <h3 className="text-lg font-semibold text-text mb-4">Save Search</h3>
        <input
          type="text"
          placeholder="Enter a name for this search..."
          value={saveSearchName}
          onChange={(e) => setSaveSearchName(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSave()}
          className="w-full px-4 py-2 bg-panel-2 border border-border text-text placeholder:text-muted rounded-md focus:outline-none focus:ring-2 focus:ring-accent mb-4"
          autoFocus
        />
        {saveError && (
          <p className="text-red-400 text-sm mb-4">{saveError}</p>
        )}
        <div className="flex justify-end gap-3">
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-panel-2 text-text-2 rounded-md hover:bg-hover transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 bg-accent hover:bg-accent/80 disabled:bg-accent/50 text-white rounded-md transition-colors"
          >
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  );
}
