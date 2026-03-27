#!/usr/bin/env python3
"""
Examples: GulpContext and GulpSource Management

This script demonstrates how to use the GulpContext and GulpSource APIs
to organize and manage data sources in GULP.
"""

import asyncio
from gulp_sdk import GulpClient


async def example_1_basic_context_operations():
    """Example 1: Create, list, update, and delete contexts."""
    print("\n" + "=" * 70)
    print("Example 1: Basic Context Operations")
    print("=" * 70)
    
    async with GulpClient("http://localhost:8080", token="admin") as client:
        # Create operation first
        op = await client.operations.create(
            name="Incident_001",
            description="Security incident investigation"
        )
        op_id = op.id
        print(f"✓ Created operation: {op_id}")
        
        # Create contexts (one per host)
        print("\n--- Creating contexts ---")
        ctx1 = await client.operations.context_create(
            operation_id=op_id,
            context_name="DC01",
            color="#0066FF",
            description="Active Directory Controller"
        )
        print(f"✓ Created context: DC01 ({ctx1['id']})")
        
        ctx2 = await client.operations.context_create(
            operation_id=op_id,
            context_name="WKS001",
            color="#00FF00",
            description="User Workstation"
        )
        print(f"✓ Created context: WKS001 ({ctx2['id']})")
        
        # List all contexts
        print("\n--- Listing contexts ---")
        contexts = await client.operations.context_list(operation_id=op_id)
        for ctx in contexts:
            print(f"  • {ctx['name']}: {ctx.get('description', 'N/A')}")
        
        # Get specific context
        print("\n--- Getting specific context ---")
        ctx = await client.operations.context_get(obj_id=ctx1['id'])
        print(f"  Context: {ctx['name']} (ID: {ctx['id']})")
        
        # Update context
        print("\n--- Updating context ---")
        updated = await client.operations.context_update(
            context_id=ctx1['id'],
            color="#FF0000",
            description="Primary DC (potentially compromised)"
        )
        print(f"✓ Updated context: {updated['description']}")
        
        # Delete context
        print("\n--- Deleting context ---")
        await client.operations.context_delete(
            context_id=ctx2['id'],
            delete_data=False  # Don't delete associated data
        )
        print(f"✓ Deleted context: WKS001")


async def example_2_basic_source_operations():
    """Example 2: Create and manage sources within contexts."""
    print("\n" + "=" * 70)
    print("Example 2: Basic Source Operations")
    print("=" * 70)
    
    async with GulpClient("http://localhost:8080", token="admin") as client:
        # Setup: Create operation and context
        op = await client.operations.create(name="Incident_002")
        op_id = op.id
        ctx = await client.operations.context_create(
            operation_id=op_id,
            context_name="FILE_SRV"
        )
        ctx_id = ctx['id']
        print(f"✓ Created operation: {op_id}")
        print(f"✓ Created context: FILE_SRV ({ctx_id})")
        
        # Create sources (one per log type)
        print("\n--- Creating sources ---")
        src_security = await client.operations.source_create(
            operation_id=op_id,
            context_id=ctx_id,
            source_name="Security",
            plugin="win_evtx",
            color="#FF0000",
            plugin_params={
                "mapping_parameters": {
                    "timestamp_field": "TimeCreated",
                    "hostname_field": "Computer"
                }
            }
        )
        print(f"✓ Created source: Security ({src_security['id']})")
        
        src_system = await client.operations.source_create(
            operation_id=op_id,
            context_id=ctx_id,
            source_name="System",
            plugin="win_evtx",
            color="#0000FF"
        )
        print(f"✓ Created source: System ({src_system['id']})")
        
        # List sources
        print("\n--- Listing sources ---")
        sources = await client.operations.source_list(
            operation_id=op_id,
            context_id=ctx_id
        )
        for src in sources:
            plugin = src.get('plugin', 'unknown')
            print(f"  • {src['name']}: {plugin}")
        
        # Get specific source
        print("\n--- Getting specific source ---")
        src = await client.operations.source_get(obj_id=src_security['id'])
        print(f"  Source: {src['name']} (ID: {src['id']})")
        print(f"  Plugin: {src.get('plugin', 'N/A')}")
        
        # Update source
        print("\n--- Updating source ---")
        updated = await client.operations.source_update(
            source_id=src_security['id'],
            color="#FF00FF",
            description="High-priority security events"
        )
        print(f"✓ Updated source: {updated.get('description', 'N/A')}")
        
        # Delete source
        print("\n--- Deleting source ---")
        await client.operations.source_delete(
            source_id=src_system['id'],
            delete_data=False
        )
        print(f"✓ Deleted source: System")


async def example_3_complete_incident_setup():
    """Example 3: Complete incident setup with multiple hosts and sources."""
    print("\n" + "=" * 70)
    print("Example 3: Complete Incident Setup")
    print("=" * 70)
    
    async with GulpClient("http://localhost:8080", token="admin") as client:
        # Create operation
        op = await client.operations.create(
            name="Ransomware_Breach_Q1_2024",
            description="Ransomware incident affecting multiple systems"
        )
        op_id = op.id
        print(f"✓ Created operation: {op_id}\n")
        
        # Define hosts and their log sources
        hosts = {
            "DC01": {
                "color": "#0066FF",
                "description": "Primary Domain Controller",
                "sources": ["Security", "System", "Application"]
            },
            "FILE_SRV": {
                "color": "#FF6600",
                "description": "File Server",
                "sources": ["Security", "System"]
            },
            "MAIL_SRV": {
                "color": "#00FF00",
                "description": "Mail Server",
                "sources": ["Security", "Application"]
            },
            "WKS001": {
                "color": "#FF00FF",
                "description": "Affected Workstation",
                "sources": ["Security", "Sysmon"]
            },
            "WKS002": {
                "color": "#FFFF00",
                "description": "Patient Zero",
                "sources": ["Security", "Sysmon", "PowerShell"]
            },
        }
        
        # Create contexts and sources
        contexts = {}
        sources_by_context = {}
        
        for host_name, host_info in hosts.items():
            # Create context
            ctx = await client.operations.context_create(
                operation_id=op_id,
                context_name=host_name,
                color=host_info["color"],
                description=host_info["description"]
            )
            ctx_id = ctx['id']
            contexts[host_name] = ctx_id
            sources_by_context[host_name] = []
            print(f"✓ Context: {host_name:12} ({ctx_id})")
            
            # Create sources for this context
            for source_name in host_info["sources"]:
                src = await client.operations.source_create(
                    operation_id=op_id,
                    context_id=ctx_id,
                    source_name=source_name,
                    plugin="win_evtx",
                    color=host_info["color"]
                )
                sources_by_context[host_name].append(src['id'])
                print(f"       └─ Source: {source_name:15} ({src['id']})")
        
        # Summary
        print("\n" + "-" * 70)
        print("SUMMARY:")
        print(f"  Operation: {op_id}")
        print(f"  Hosts: {len(contexts)}")
        print(f"  Total Sources: {sum(len(s) for s in sources_by_context.values())}")
        
        print("\nHost breakdown:")
        for host in contexts.keys():
            source_count = len(sources_by_context[host])
            print(f"  • {host}: {source_count} sources")


async def example_4_error_handling():
    """Example 4: Error handling and best practices."""
    print("\n" + "=" * 70)
    print("Example 4: Error Handling")
    print("=" * 70)
    
    async with GulpClient("http://localhost:8080", token="admin") as client:
        # Create operation for testing
        op = await client.operations.create(name="Error_Test_Op")
        op_id = op.id
        
        # Example 1: Idempotent creation
        print("\n--- Idempotent Context Creation ---")
        ctx1 = await client.operations.context_create(
            operation_id=op_id,
            context_name="TestHost",
            fail_if_exists=False  # Default: returns existing if found
        )
        print(f"✓ First creation: {ctx1['id']}")
        
        ctx2 = await client.operations.context_create(
            operation_id=op_id,
            context_name="TestHost",
            fail_if_exists=False
        )
        print(f"✓ Second creation: {ctx2['id']} (same as first)")
        
        # Example 2: Failure on duplicate
        print("\n--- Fail on Duplicate ---")
        try:
            ctx3 = await client.operations.context_create(
                operation_id=op_id,
                context_name="TestHost",
                fail_if_exists=True  # Fails if exists
            )
        except Exception as e:
            print(f"✗ Expected error: {type(e).__name__}")
            print(f"  Message: {str(e)}")
        
        # Example 3: Update validation
        print("\n--- Update Validation ---")
        try:
            # Must provide at least one field to update
            await client.operations.context_update(
                context_id=ctx1['id']
                # No fields provided
            )
        except ValueError as e:
            print(f"✗ Expected error: {str(e)}")
        
        print(f"\n✓ Skipping cleanup to preserve test context")


async def example_5_hierarchical_query():
    """Example 5: Query data hierarchically (operation → context → source)."""
    print("\n" + "=" * 70)
    print("Example 5: Hierarchical Data Organization")
    print("=" * 70)
    
    async with GulpClient("http://localhost:8080", token="admin") as client:
        # Create operation with structure
        op = await client.operations.create(name="Query_Demo")
        op_id = op.id
        
        # Create context
        ctx = await client.operations.context_create(
            operation_id=op_id,
            context_name="WebServer"
        )
        ctx_id = ctx['id']
        
        # Create sources
        src1 = await client.operations.source_create(
            operation_id=op_id,
            context_id=ctx_id,
            source_name="Apache_Access"
        )
        
        src2 = await client.operations.source_create(
            operation_id=op_id,
            context_id=ctx_id,
            source_name="Apache_Error"
        )
        
        print(f"Operation: {op_id}")
        print(f"  └─ Context: {ctx['name']} ({ctx_id})")
        print(f"     ├─ Source: {src1['name']} ({src1['id']})")
        print(f"     └─ Source: {src2['name']} ({src2['id']})")
        
        # Retrieve hierarchical data
        print("\n--- Retrieving Hierarchical Data ---")
        op_data = await client.operations.get(op_id)
        print(f"\n1. Operation: {op_data.name} ({op_data.id})")
        
        contexts = await client.operations.context_list(operation_id=op_id)
        for ctx in contexts:
            print(f"   └─ Context: {ctx['name']} ({ctx['id']})")
            
            sources = await client.operations.source_list(
                operation_id=op_id,
                context_id=ctx['id']
            )
            for src in sources:
                print(f"      └─ Source: {src['name']} ({src['id']})")


async def main():
    """Run all examples."""
    examples = [
        example_1_basic_context_operations,
        example_2_basic_source_operations,
        example_3_complete_incident_setup,
        example_4_error_handling,
        example_5_hierarchical_query,
    ]
    
    for example in examples:
        try:
            await example()
        except Exception as e:
            print(f"\n✗ Example failed: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("All examples completed!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
