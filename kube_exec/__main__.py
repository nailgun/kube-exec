import re
import sys
import argparse
import subprocess

import kubernetes
import kubernetes.client.rest


class Resource:
    def __init__(self, api, descriptor):
        self.api = api
        self.descriptor = descriptor

    def __repr__(self):
        return repr(self.descriptor)


def main():
    args, unknown_args = get_args_parser().parse_known_args()

    if '/' in args.object:
        kind, name = args.object.split('/', maxsplit=1)
        kind = kind.lower()
    else:
        kind, name = 'deployment', args.object

    kubernetes.config.load_kube_config()

    kind2resource_map = get_kind2resource_map()
    resource = kind2resource_map.get(kind)
    if not resource:
        print('Invalid kind:', kind, file=sys.stderr)
        return sys.exit(1)

    api = resource.api
    getter = getattr(api, 'read_namespaced_' + camel2snake(resource.descriptor.kind))
    try:
        obj = getter(name, args.namespace)
    except kubernetes.client.rest.ApiException as e:
        if e.status == 404:
            print(kind, name, 'does not exist in namespace', args.namespace, file=sys.stderr)
            return sys.exit(1)
        else:
            raise

    if not hasattr(obj.spec, 'selector'):
        print('Unsupported kind:', kind, file=sys.stderr)
        return sys.exit(1)

    label_selector = ','.join('{}={}'.format(k, v) for k, v in obj.spec.selector.match_labels.items())
    pods = kubernetes.client.CoreV1Api().list_namespaced_pod(args.namespace, label_selector=label_selector).items
    pods = [pod.metadata.name for pod in pods]

    if not pods:
        print('No running pods with selector', label_selector, file=sys.stderr)
        return sys.exit(1)

    pod = pods[0]
    print('Executing command in pod', pod, file=sys.stderr)

    kubectl_args = [
        'kubectl',
        'exec',
        '--namespace',
        args.namespace,
    ] + unknown_args + [
        pod,
        '--'
    ] + args.command

    result = subprocess.run(kubectl_args)
    sys.exit(result.returncode)


def get_args_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('-n', '--namespace', default='default')
    parser.add_argument('object')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    return parser


def get_kind2resource_map():
    name2resource_map = {}
    for api_class in kubernetes.client.__dict__.values():
        if hasattr(api_class, 'get_api_resources'):
            api = api_class()

            try:
                response = api.get_api_resources()
            except kubernetes.client.rest.ApiException as e:
                if e.status == 404:
                    continue
                raise e

            for descriptor in response.resources:
                resource = Resource(api, descriptor)
                name2resource_map[descriptor.kind.lower()] = resource
                if descriptor.short_names:
                    for short_name in descriptor.short_names:
                        name2resource_map[short_name] = resource
    return name2resource_map


def camel2snake(name):
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()


if __name__ == '__main__':
    main()
