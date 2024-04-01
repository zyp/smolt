#pragma once

#include <bit>
#include <array>
#include <string_view>
#include <algorithm>
#include <source_location>
#include <concepts>
#include <cstdint>
#include <cstring>
#include <span>
#include <string_view>

namespace smolt {
    // Internal utilities.
    namespace util {
        using str_buf = std::array<char, 256>;

        constexpr auto make_str_buf(std::string_view s) {
            str_buf buf {};
            std::copy(s.begin(), s.end(), buf.begin());
            return buf;
        }
    }

    // Type markers.
    namespace type {
        // Boolean.
        struct b {};

        template <std::same_as<bool> T>
        constexpr b mark(T) {
            return {};
        }

        constexpr void is_marked(b) {}

        // Unsigned integral.
        template <std::size_t N>
        struct u {};

        template <std::unsigned_integral T>
        constexpr u<sizeof(T) * 8> mark(T) requires (!std::same_as<T, bool>) {
            return {};
        }

        template <std::size_t N>
        constexpr void is_marked(u<N>) {}

        // Signed integral.
        template <std::size_t N>
        struct s {};

        template <std::signed_integral T>
        constexpr s<sizeof(T) * 8> mark(T) {
            return {};
        }

        template <std::size_t N>
        constexpr void is_marked(s<N>) {}

        // Floating point.
        template <std::size_t N>
        struct f {};

        template <std::floating_point T>
        constexpr f<sizeof(T) * 8> mark(T) {
            return {};
        }

        template <std::size_t N>
        constexpr void is_marked(f<N>) {}

        // Span.
        template <typename T, std::size_t E>
        struct span {};

        template <typename T, std::size_t E>
        constexpr span<decltype(mark(T{})), E> mark(std::span<T, E>) {
            return {};
        }

        template <typename T, std::size_t E>
        constexpr void is_marked(span<T, E>) {}

        // String.
        template <typename T>
        struct string {};

        template <typename T>
        constexpr string<decltype(mark(T{}))> mark(std::basic_string_view<T>) {
            return {};
        }

        template <typename T>
        constexpr void is_marked(string<T>) {}

        // Concept.
        template <typename T>
        concept marked = requires(T t) {
            { is_marked(t) };
        };
    }

    // Metadata containers.
    namespace meta {
        // Format string.
        struct fmt_v0 {
            util::str_buf fmt;
            constexpr fmt_v0(const char* s) : fmt(util::make_str_buf(s)) {}
        };

        // Source location.
        struct loc_v0 {
            util::str_buf filename;
            unsigned line;
        };

        // Format arguments.
        template <type::marked... T>
        struct args_v0 {};
    }

    // Concepts.
    namespace concepts {
        constexpr void is_meta(meta::fmt_v0) {}
        constexpr void is_meta(meta::loc_v0) {}
        template <typename... T>
        constexpr void is_meta(meta::args_v0<T...>) {}

        template <typename T>
        concept meta = requires(T t) {
            { is_meta(t) };
        };

        template <typename T>
        concept transport = requires(T t, uint32_t v) {
            { t.log_tag(v) };
            { t.log_value(v) };
        };

        template <typename T>
        concept has_enabled = requires(T t) {
            { t.enabled() } -> std::same_as<bool>;
        };
    }

    // Tag creation.
    struct tag_marker {};
    using tag_id = void (*)(tag_marker);

    template <auto... t>
    void tag(tag_marker) {
        static_assert ((concepts::meta<decltype(t)> && ...), "Argument is not a valid tag metadata type.");
    }

    // Transports.
    namespace transport {
        struct blackhole {
            void log_tag(uint32_t) const {}
            void log_value(uint32_t) const {}
        };

        struct itm {
            uint8_t channel = 24;

            volatile uint32_t* reg_stim() const {
                return reinterpret_cast<volatile uint32_t*>(0xe0000000);
            }

            volatile uint32_t* reg_ter() const {
                return reinterpret_cast<volatile uint32_t*>(0xe0000e00);
            }

            bool enabled() const {
                return ((reg_ter()[channel / 32] >> (channel % 32)) & 3) == 3;
            }

            // TODO: We could potentially lose a write due to the FIFO being full if preempted between the check and the write.
            // ARM manual suggests using ldrex/strex.

            void log_tag(uint32_t tag) const {
                while((reg_stim()[channel] & 1) == 0);
                reg_stim()[channel] = tag;
            }
            void log_value(uint32_t value) const {
                while((reg_stim()[channel + 1] & 1) == 0);
                reg_stim()[channel + 1] = value;
            }
        };

        template <std::size_t depth>
        struct ringbuffer {
            std::array<uint32_t, depth> data;
            std::size_t write_idx;
            std::size_t tag_idx;

            void log_tag(uint32_t tag) {
                log_value(tag);
                tag_idx = write_idx;
            }

            void log_value(uint32_t value) {
                write_idx = write_idx ? write_idx - 1 : depth - 1;
                data[write_idx] = value;
            }
        };
    }

    // Loggable info.
    namespace info {
        constexpr meta::loc_v0 loc(std::source_location location = std::source_location::current()) {
            return {
                util::make_str_buf(location.file_name()),
                location.line(),
            };
        }
    }

    // Serializers.
    namespace serializer {
        // Tag ID.
        template <concepts::transport transport_t>
        constexpr void serialize_tag(transport_t& transport, tag_id id) {
            transport.log_tag(static_cast<uint32_t>(std::bit_cast<uintptr_t>(id)));
        }

        // Integral types <= 32b.
        template <concepts::transport transport_t, std::integral T>
        constexpr void serialize(transport_t& transport, T value) requires (sizeof(T) <= sizeof(uint32_t)) {
            transport.log_value(static_cast<uint32_t>(value));
        }

        // float.
        template <concepts::transport transport_t, typename T>
        constexpr void serialize(transport_t& transport, T value) requires std::same_as<T, float> {
            transport.log_value(std::bit_cast<uint32_t>(value));
        }

        // 64b integers and double.
        template <concepts::transport transport_t, typename T>
        constexpr void serialize(transport_t& transport, T value) requires (std::same_as<T, std::int64_t> || std::same_as<T, std::uint64_t> || std::same_as<T, double>) {
            uint64_t buf = std::bit_cast<uint64_t>(value);

            transport.log_value(static_cast<uint32_t>(buf >> 32));
            transport.log_value(static_cast<uint32_t>(buf));
        }

        // std::span.
        template <concepts::transport transport_t, typename T, std::size_t Extent>
        constexpr void serialize(transport_t& transport, std::span<T, Extent> data) {
            auto bytes = std::as_bytes(data);
            for(std::size_t offset = (bytes.size() + 3) & ~3; offset;) {
                offset -= 4;
                auto chunk = bytes.subspan(offset, std::min<std::size_t>(4, bytes.size() - offset));
                uint32_t value = 0;
                std::memcpy(&value, chunk.data(), chunk.size());
                transport.log_value(value);
            }

            if (data.extent == std::dynamic_extent) {
                transport.log_value(data.size());
            }
        }

        // std::basic_string_view.
        template <concepts::transport transport_t, typename T>
        constexpr void serialize(transport_t& transport, std::basic_string_view<T> data) {
            serialize(transport, std::span(data));
        }
    }

    // Logger.
    template <concepts::transport transport_t>
    struct logger {
        transport_t transport;

        constexpr void log_values() const {}

        template <typename T, typename... U>
        constexpr void log_values(T arg, U... args) const {
            log_values(args...);
            serializer::serialize(transport, arg);
        }

        template <typename... T>
        constexpr void log_internal(tag_id id, T... args) const {
            if constexpr (concepts::has_enabled<transport_t>) {
                if (!transport.enabled()) {
                    return;
                }
            }

            log_values(args...);
            serializer::serialize_tag(transport, id);
        }

        // Format string and arguments.
        template <meta::fmt_v0 str, typename... T>
        constexpr void log(T... args) const {
            log_internal(tag<str, meta::args_v0<decltype(type::mark(args))...>{}>, args...);
        }

        // Format string, location and arguments.
        template <meta::fmt_v0 str, meta::loc_v0 loc, typename... T>
        constexpr void log(T... args) const {
            log_internal(tag<str, loc, meta::args_v0<decltype(type::mark(args))...>{}>, args...);
        }

        // Location only.
        template <meta::loc_v0 loc>
        constexpr void log() const {
            log_internal(tag<loc>);
        }
    };

    // Do the right thing whether the transport is passed as a reference or a rvalue.
    template <concepts::transport transport_t>
    logger(transport_t&&) -> logger<transport_t>;
}
