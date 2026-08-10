import {
  Button,
  Dialog,
  DialogActions,
  DialogBody,
  DialogContent,
  DialogSurface,
  DialogTitle,
  Text,
} from "@fluentui/react-components";

import { OUTPUT_TEMPLATES, type OutputTemplateKey } from "./OutputTemplates";

type Props = {
  output: OutputTemplateKey;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export function OutputTemplateDialog({ output, open, onOpenChange }: Props) {
  const template = OUTPUT_TEMPLATES[output];

  return (
    <Dialog open={open} onOpenChange={(_, data) => onOpenChange(data.open)}>
      <DialogSurface aria-label={`${template.title} 示例`}>
        <DialogBody>
          <DialogTitle>{template.title} 示例</DialogTitle>
          <DialogContent className="output-template-dialog">
            <Text>{template.description}</Text>
            <Text className="output-template-dialog__best-for">{template.bestFor}</Text>
            <pre aria-label={`${template.title} 模板内容`}>{template.sample}</pre>
          </DialogContent>
          <DialogActions>
            <Button appearance="secondary" onClick={() => onOpenChange(false)}>关闭</Button>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}
