import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.mysql_client import MySQLClient
import json

def main():
    # 创建MySQL客户端
    client = MySQLClient()

    # 读取mc_data.json文件
    data_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'mc_data.json')

    try:
        with open(data_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"读取到 {len(data)} 条数据")

        # 统计各分类数量
        categories = {}
        for item in data:
            category = item.get('metadata', {}).get('category', 'general')
            categories[category] = categories.get(category, 0) + 1

        print("分类统计:")
        for cat, count in categories.items():
            print(f"  {cat}: {count}")

        # 批量插入数据
        print("\n开始批量插入数据...")
        inserted_count = client.batch_insert_knowledge(data)
        print(f"成功插入 {inserted_count} 条数据")

        # 验证数据
        print("\n验证数据插入...")
        total_count = client.search_knowledge("", limit=1000)
        print(f"数据库中共有 {len(total_count)} 条知识")

        # 测试搜索功能
        print("\n测试搜索功能...")
        test_queries = ["末地", "音乐", "方块"]
        for query in test_queries:
            results = client.search_knowledge(query, limit=3)
            print(f"搜索 '{query}' 找到 {len(results)} 条结果")
            for i, result in enumerate(results[:2], 1):
                print(f"  {i}. {result['title']} ({result['category']})")

        # 获取统计信息
        print("\n获取统计信息...")
        stats = client.get_query_stats(hours=24)
        print("24小时统计:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print("\n热门分类:")
        popular_cats = client.get_popular_categories(limit=5)
        for cat in popular_cats:
            print(f"  {cat['category']}: {cat['count']} 条")

    except FileNotFoundError:
        print(f"数据文件不存在: {data_file}")
    except Exception as e:
        print(f"处理数据时出错: {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()