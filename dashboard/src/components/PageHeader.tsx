import type { ReactNode } from "react";
import { Text } from "@fluentui/react-components";

export function PageHeader({ title, description, actions }: {
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return <header className="page-header">
    <div>
      <Text as="h1" size={700} block>{title}</Text>
      {description && <Text className="page-header__description" block>{description}</Text>}
    </div>
    {actions && <div className="page-header__actions">{actions}</div>}
  </header>;
}
