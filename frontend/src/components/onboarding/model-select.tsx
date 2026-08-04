"use client";

import { Check, ChevronDown } from "lucide-react";
import {
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { QUANT_MODELS } from "@/mocks/models";

interface ModelSelectProps {
  value: string | null;
  onChange(value: string): void;
}

export function ModelSelect({ value, onChange }: ModelSelectProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();
  const [isOpen, setIsOpen] = useState(false);
  const selectedIndex = QUANT_MODELS.findIndex((model) => model.id === value);
  const [activeIndex, setActiveIndex] = useState(
    selectedIndex >= 0 ? selectedIndex : 0,
  );
  const selectedModel = selectedIndex >= 0 ? QUANT_MODELS[selectedIndex] : null;

  useEffect(() => {
    function handleOutside(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("pointerdown", handleOutside);
    return () => document.removeEventListener("pointerdown", handleOutside);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    const activeOption = listRef.current?.querySelector<HTMLElement>(
      `[data-index="${activeIndex}"]`,
    );
    activeOption?.scrollIntoView({ block: "nearest" });
  }, [activeIndex, isOpen]);

  function open() {
    setActiveIndex(selectedIndex >= 0 ? selectedIndex : 0);
    setIsOpen(true);
  }

  function choose(index: number) {
    onChange(QUANT_MODELS[index].id);
    setActiveIndex(index);
    setIsOpen(false);
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>) {
    if (!isOpen && ["Enter", " ", "ArrowDown"].includes(event.key)) {
      event.preventDefault();
      open();
      return;
    }

    if (!isOpen) return;

    if (event.key === "Escape") {
      event.preventDefault();
      setIsOpen(false);
    } else if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((current) => Math.min(current + 1, QUANT_MODELS.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((current) => Math.max(current - 1, 0));
    } else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      choose(activeIndex);
    } else if (event.key === "Home") {
      event.preventDefault();
      setActiveIndex(0);
    } else if (event.key === "End") {
      event.preventDefault();
      setActiveIndex(QUANT_MODELS.length - 1);
    }
  }

  return (
    <div className="qb-model-select" ref={rootRef}>
      <button
        type="button"
        role="combobox"
        aria-expanded={isOpen}
        aria-controls={listboxId}
        aria-haspopup="listbox"
        aria-activedescendant={isOpen ? `${listboxId}-${activeIndex}` : undefined}
        className="qb-model-trigger"
        onClick={() => (isOpen ? setIsOpen(false) : open())}
        onKeyDown={handleKeyDown}
      >
        <span className={selectedModel ? "" : "is-placeholder"}>
          {selectedModel?.name ?? "选择模型（共 23 个）"}
        </span>
        <ChevronDown aria-hidden="true" className={isOpen ? "is-open" : ""} />
      </button>

      {isOpen ? (
        <div
          id={listboxId}
          ref={listRef}
          role="listbox"
          aria-label="量化模型"
          className="qb-model-menu"
          onWheel={(event) => event.stopPropagation()}
        >
          {QUANT_MODELS.map((model, index) => {
            const isSelected = model.id === value;
            return (
              <button
                key={model.id}
                id={`${listboxId}-${index}`}
                type="button"
                role="option"
                aria-selected={isSelected}
                data-index={index}
                className={`qb-model-option ${activeIndex === index ? "is-active" : ""}`}
                onPointerEnter={() => setActiveIndex(index)}
                onClick={() => choose(index)}
              >
                <span className="qb-model-option-top">
                  <strong>{model.name}</strong>
                  {isSelected ? <Check aria-hidden="true" /> : null}
                </span>
                <span className="qb-model-tags">
                  {model.tags.map((tag) => <i key={tag}>{tag}</i>)}
                </span>
                <span className="qb-model-description">{model.description}</span>
              </button>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
