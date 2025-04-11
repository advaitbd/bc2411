import React from "react";
import { X } from "lucide-react";

interface ModalProps {
  title: string;
  onClose: () => void;
  onSubmit: (e: React.FormEvent) => void;
  submitText: string;
  children: React.ReactNode;
  error: string | null;
}

const Modal: React.FC<ModalProps> = ({
  title,
  onClose,
  onSubmit,
  submitText,
  children,
  error,
}) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-70 flex items-center justify-center z-50 p-4 backdrop-blur-sm">
      <div className="bg-gray-800 p-6 rounded-xl w-full max-w-lg shadow-2xl border border-gray-700 max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6 sticky top-0 bg-gray-800 pt-1 pb-3 -mt-1 z-10">
          <h3 className="text-2xl font-semibold">{title}</h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white transition-colors p-1 rounded-full hover:bg-gray-700"
          >
            <X className="w-6 h-6" />
          </button>
        </div>
        <form onSubmit={onSubmit} className="space-y-4 pb-2">
          {children}
          {error && (
            <div className="bg-red-900 border border-red-700 text-red-300 px-3 py-2 rounded text-sm mt-2">
              {error}
            </div>
          )}
          <button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700 py-2.5 rounded-lg mt-6 transition-colors font-semibold text-base"
          >
            {submitText}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Modal;