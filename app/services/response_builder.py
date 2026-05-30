from app.schemas.search_context import SearchContext


def build_response(context: SearchContext, user_id: str, response_type: str):
    items = context.items[:5]

    serialized_items = [
        item if isinstance(item, dict) else {
            "id": item.id,
            "sku": item.sku,
            "name": item.name,
            "price": item.price,
        }
        for item in items
    ]

    shown = len(serialized_items)
    has_more = context.total_count > (context.offset + shown)
    next_offset = context.offset + shown if has_more else None

    response = {
        "type": response_type,
        "data": {
            "user_id": user_id,
            "results": {
    "query": context.query,
    "matched_by": context.matched_by,
    "search_strategy": context.search_strategy,
    "items": serialized_items,
    "total": context.total_count,
    "shown": shown,
    "has_more": has_more,
    "next_offset": next_offset,
},
        },
    }

    if context.total_count == 0:
        response["message"] = "No products found"
        return response


    if context.detected_color:
        response["message"] = (
            f"I found {context.total_count} products, "
            f"but I cannot verify color '{context.detected_color}' yet "
            "because product color data is not available in the catalog."
        )
        return response

    # message logic

    elif context.matched_by == "brand_fallback":
        response["message"] = (
            f"Exact match for '{context.query}' was not found. "
            f"Showing alternative products for '{context.normalized_query}'."
        )


    if context.result_mode == "need_size":
        response["message"] = (
            f"I found options for '{context.model_hint}'. "
            "Could you specify the size?"
        )




    elif context.result_mode == "need_model":

        if context.total_count == 1:

            response["message"] = (

                "I found one product that matches the brand and size. "

                "If you need a specific model, you can send the model name, SKU, product link, or photo."

            )

        else:

            response["message"] = (

                f"I found {context.total_count} matching products in this size. "

                "Could you specify the exact model? "

                "You can send a SKU, product name, photo, or link. "

                f"Here are {len(serialized_items)} options to start with."

            )


    elif context.matched_by == "size_alternatives":
        response["message"] = (
            "Exact brand or model was not found in this size. "
            f"Showing alternative products available in size {context.detected_size}."
        )



    elif context.result_mode == "exact_model_match":
        response["message"] = (
            f"Showing results for '{context.model_hint}'. "
            f"Here are top {len(serialized_items)} options."
        )

    elif context.result_mode == "fallback_similar":
        response["message"] = (
            f"We couldn't find exact '{context.model_hint}' models, "
            f"but here are similar options. "
            f"Here are {len(serialized_items)} options to start with."
        )




    elif context.result_mode == "broad_query":
        response["message"] = (
            f"I found {context.total_count} matching products. "
            "Could you specify what you are looking for — model, size, or gender? "
            f"Here are {len(serialized_items)} options to start with."
        )


    elif context.total_count == 1:
        response["message"] = "Found one product"

    else:
        response["message"] = (
            f"Found {context.total_count} products. "
            f"Showing top {len(serialized_items)}."
        )
    return response