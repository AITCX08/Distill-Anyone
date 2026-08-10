import { Button, Checkbox, Text } from "@fluentui/react-components";

import { OUTPUT_TEMPLATES, type OutputTemplateKey } from "./OutputTemplates";

type Props = {
  output: OutputTemplateKey;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  onShowTemplate: () => void;
};

export function OutputSelectionCard({ output, checked, onCheckedChange, onShowTemplate }: Props) {
  const template = OUTPUT_TEMPLATES[output];
  return (
    <article className="output-selection-card">
      <Checkbox
        label={template.title}
        checked={checked}
        onChange={(_, data) => onCheckedChange(!!data.checked)}
      />
      <Text>{template.description}</Text>
      <Text className="output-selection-card__best-for">{template.bestFor}</Text>
      <Button appearance="subtle" onClick={onShowTemplate}>查看 {template.title} 示例</Button>
    </article>
  );
}
