import { Badge, Divider, Group, Text, Tooltip } from '@mantine/core';

import { formatMoney } from '../lib/money';
import type { PersonBalance } from '../lib/people';

export function PersonRow({ person }: { person: PersonBalance }) {
    const [first, ...rest] = person.amounts;

    return (
        <>
            <Group justify='space-between' py='md' px='sm'>
                <Group gap='sm'>
                    <Text>{person.name}</Text>
                    {person.isLocal && (
                        <Badge
                            variant='light'
                            color='gray'
                            tt='none'
                            fw={400}
                            radius='sm'
                        >
                            local
                        </Badge>
                    )}
                </Group>

                <Group gap='xs'>
                    <Text fw={600}>
                        {formatMoney(first.net_minor, first.currency, {
                            sign: true,
                        })}
                    </Text>
                    {rest.length > 0 && (
                        <Tooltip
                            label={rest
                                .map((a) =>
                                    formatMoney(a.net_minor, a.currency, {
                                        sign: true,
                                    }),
                                )
                                .join(' | ')}
                        >
                            <Badge
                                variant='light'
                                color='gray'
                                fw={400}
                                radius='sm'
                            >
                                +{rest.length}
                            </Badge>
                        </Tooltip>
                    )}
                </Group>
            </Group>
            <Divider />
        </>
    );
}
