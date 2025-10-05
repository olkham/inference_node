#!/usr/bin/env python3
"""
InferNode - Main entry point for the scalable inference platform
"""

def main():
    """Main entry point for the InferNode application."""
    import sys
    import os
    
    # Add the current directory to the path to ensure imports work
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    
    # Import and run the inference node
    from InferenceNode.inference_node import InferenceNode
    import argparse
    
    parser = argparse.ArgumentParser(description='InferNode - Scalable Inference Platform')
    parser.add_argument('--port', type=int, default=5555, help='Web interface port (default: 5555)')
    parser.add_argument('--name', type=str, help='Node name (default: auto-generated)')
    parser.add_argument('--no-discovery', action='store_true', help='Disable network discovery')
    parser.add_argument('--no-telemetry', action='store_true', help='Disable telemetry')
    parser.add_argument('--production', action='store_true', help='Run in production mode with Waitress WSGI server')
    
    args = parser.parse_args()
    
    # Create node
    node = InferenceNode(args.name, port=args.port)
    
    try:
        enable_discovery = not args.no_discovery
        enable_telemetry = not args.no_telemetry
        node.start(enable_discovery=enable_discovery, enable_telemetry=enable_telemetry, production=args.production)
    except KeyboardInterrupt:
        print("\nShutting down InferNode...")
        node.stop()
    except Exception as e:
        print(f"Error: {e}")
        node.stop()
        sys.exit(1)


if __name__ == "__main__":
    main()
